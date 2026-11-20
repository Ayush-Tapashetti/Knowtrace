"""Students, practice attempts, mastery heatmap and trajectory forecasts."""

from __future__ import annotations

from knowtrace.domain.bkt import apply_time_forgetting
from knowtrace.domain.enums import AttemptContext
from knowtrace.domain.errors import UnknownConceptError
from knowtrace.domain.forecast import (
    forecast_interval,
    forecast_mastery,
    predict_next_correct,
    time_to_mastery,
)
from knowtrace.models import Student
from knowtrace.models._base import new_id
from knowtrace.repositories import learners as repo
from knowtrace.services import diagnoses
from knowtrace.services.attempts import mastery_map, record_attempt, require_student
from knowtrace.services.context import Ctx
from knowtrace.services.errors import ConflictError
from knowtrace.services.views import (
    AttemptResult,
    ForecastPoint,
    ForecastView,
    MasteryPoint,
    MasteryView,
    StudentView,
)

MAX_HORIZON = 60
_SECONDS_PER_DAY = 86_400.0


def create_student(ctx: Ctx, pseudonym: str | None) -> StudentView:
    name = pseudonym or f"student-{new_id()[:8]}"
    if repo.pseudonym_taken(ctx.session, name):
        raise ConflictError(f"pseudonym already in use: {name!r}", details={"pseudonym": name})
    s = repo.add_student(ctx.session, Student(pseudonym=name, created_at=ctx.now))
    ctx.commit()
    return StudentView(s.id, s.pseudonym, s.created_at)


def get_student(ctx: Ctx, student_id: str) -> StudentView:
    require_student(ctx, student_id)
    s = repo.get_student(ctx.session, student_id)
    assert s is not None
    return StudentView(s.id, s.pseudonym, s.created_at)


def mastery_view(ctx: Ctx, student_id: str) -> MasteryView:
    """Mastery per concept with time forgetting applied on read (never stored)."""
    require_student(ctx, student_id)
    b, theta = ctx.bundle, ctx.cfg.theta_master
    stored = repo.mastery_rows(ctx.session, student_id)
    points: list[MasteryPoint] = []
    for cid in b.graph.order:
        spec, row = b.graph.concepts[cid], stored.get(cid)
        p, n, seen = spec.p_init, 0, None
        if row is not None:
            p, n, seen = row.p_mastery, row.n_obs, row.last_observed_at
            if seen is not None:
                days = (ctx.now - seen).total_seconds() / _SECONDS_PER_DAY
                p = apply_time_forgetting(p, days, spec.half_life_days, spec.p_init)
        points.append(MasteryPoint(cid, b.name(cid), p, n, p >= theta, seen))
    return MasteryView(student_id, theta, points)


def submit_practice(
    ctx: Ctx, student_id: str, item_id: str, answer: str, latency_ms: int | None
) -> AttemptResult:
    require_student(ctx, student_id)
    live = diagnoses.live_diagnosis(ctx, student_id)
    if live is not None:
        raise ConflictError(
            "finish or abandon the open diagnosis before practising",
            details={"diagnosis_id": live.id, "state": live.state.value},
        )
    before = mastery_map(ctx, student_id)
    attempt, view = record_attempt(ctx, student_id, item_id, answer, latency_ms, AttemptContext.PRACTICE)
    opened = (
        None if attempt.is_correct else diagnoses.open_for_failed_attempt(ctx, student_id, attempt, before)
    )
    ctx.commit()
    return AttemptResult(view, diagnoses.view(ctx, opened) if opened else None)


def forecast_view(ctx: Ctx, student_id: str, concept_id: str, horizon: int) -> ForecastView:
    require_student(ctx, student_id)
    b, cfg = ctx.bundle, ctx.cfg
    if concept_id not in b.graph.concepts:
        raise UnknownConceptError(concept_id)
    spec = b.graph.concepts[concept_id]
    mastery = mastery_map(ctx, student_id)
    p0 = mastery[concept_id]
    n_obs = repo.mastery_rows(ctx.session, student_id).get(concept_id)
    n_eff = cfg.forecast_k0 + (n_obs.n_obs if n_obs else 0)
    points = []
    for k in range(horizon + 1):
        p = forecast_mastery(p0, spec.p_learn, spec.p_forget, k)
        lo, hi = forecast_interval(p, n_eff)
        points.append(ForecastPoint(k, p, min(lo, p), max(hi, p)))
    return ForecastView(
        student_id=student_id,
        concept_id=concept_id,
        concept_name=b.name(concept_id),
        current_mastery=p0,
        theta_master=cfg.theta_master,
        points=points,
        steps_to_mastery=time_to_mastery(p0, spec.p_learn, spec.p_forget, cfg.theta_master, MAX_HORIZON),
        p_next_correct=predict_next_correct([concept_id], mastery, spec.p_slip, spec.p_guess),
    )
