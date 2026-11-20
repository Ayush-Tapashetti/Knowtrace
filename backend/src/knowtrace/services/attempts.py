"""Recording graded attempts: the one place that grades, updates mastery and rolls forecasts."""

from __future__ import annotations

from collections.abc import Mapping

from knowtrace.domain.bkt import clamp_prob, update_mastery_from_attempt
from knowtrace.domain.enums import AttemptContext
from knowtrace.domain.forecast import forecast_interval, forecast_mastery, predict_next_correct
from knowtrace.domain.grading import grade_answer
from knowtrace.models import Attempt, ForecastRecord
from knowtrace.repositories import diagnoses as diag_repo
from knowtrace.repositories import learners as repo
from knowtrace.services.context import Ctx
from knowtrace.services.errors import NotFoundError
from knowtrace.services.views import AttemptView


def require_student(ctx: Ctx, student_id: str) -> None:
    if repo.get_student(ctx.session, student_id) is None:
        raise NotFoundError("student", student_id)


def mastery_map(ctx: Ctx, student_id: str) -> dict[str, float]:
    """Stored mastery for every concept, falling back to each concept's prior."""
    stored = repo.mastery_rows(ctx.session, student_id)
    graph = ctx.bundle.graph
    return {
        cid: stored[cid].p_mastery if cid in stored else spec.p_init for cid, spec in graph.concepts.items()
    }


def _roll_forecasts(ctx: Ctx, student_id: str, attempt: Attempt, mastery: Mapping[str, float]) -> None:
    """Resolve open forecasts with this outcome, then record a fresh one per touched concept (D2)."""
    graph, cfg = ctx.bundle.graph, ctx.cfg
    rows = repo.mastery_rows(ctx.session, student_id)
    for cid in ctx.bundle.qmatrix[attempt.item_id].concepts:
        for old in diag_repo.unresolved_forecasts(ctx.session, student_id, cid):
            old.observed_correct, old.resolved_attempt_id = attempt.is_correct, attempt.id
            ctx.session.add(old)
        spec = graph.concepts[cid]
        p1 = clamp_prob(forecast_mastery(mastery[cid], spec.p_learn, spec.p_forget, 1))
        n_eff = cfg.forecast_k0 + (rows[cid].n_obs if cid in rows else 0)
        lo, hi = forecast_interval(p1, n_eff)
        diag_repo.add_forecast(
            ctx.session,
            ForecastRecord(
                student_id=student_id,
                concept_id=cid,
                made_at_seq=attempt.seq,
                p_mastery_pred=p1,
                p_lo=min(lo, p1),
                p_hi=max(hi, p1),
                p_correct_pred=clamp_prob(predict_next_correct([cid], mastery, spec.p_slip, spec.p_guess)),
            ),
        )


def record_attempt(
    ctx: Ctx,
    student_id: str,
    item_id: str,
    answer: str,
    latency_ms: int | None,
    context: AttemptContext,
    diagnosis_id: str | None = None,
) -> tuple[Attempt, AttemptView]:
    """Grade server-side, append to the attempt log, update mastery, roll forecasts. No commit."""
    b = ctx.bundle
    if item_id not in b.items:
        raise NotFoundError("item", item_id)
    correct = grade_answer(b.items[item_id], answer)  # InvalidAnswerError -> 422
    before = mastery_map(ctx, student_id)
    attempt = repo.add_attempt(
        ctx.session,
        Attempt(
            student_id=student_id,
            seq=repo.next_seq(ctx.session, student_id),
            item_id=item_id,
            context=context,
            diagnosis_id=diagnosis_id,
            answer_given=answer,
            is_correct=correct,
            latency_ms=latency_ms,
            attempted_at=ctx.now,
        ),
    )
    row = b.qmatrix[item_id]
    after = update_mastery_from_attempt(
        before, b.items[item_id], list(row.concepts), b.graph.concepts, correct
    )
    touched = {cid: after[cid] for cid in row.concepts}
    repo.upsert_mastery(ctx.session, student_id, touched, ctx.now, ctx.now)
    _roll_forecasts(ctx, student_id, attempt, after)
    return attempt, AttemptView(attempt.id, attempt.seq, item_id, context, correct, touched)
