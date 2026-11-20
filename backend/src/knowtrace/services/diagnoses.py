"""Diagnosis episodes over HTTP: open on a failed attempt, probe adaptively, assign a lesson, recheck.

The maths lives in `domain/`; this module only loads rows, calls the pure functions, applies the
state machine, and persists the outcome.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict

from knowtrace.domain.bkt import effective_item_params
from knowtrace.domain.diagnosis import (
    candidate_set,
    diagnosis_verdict,
    expected_information_gain,
    explain_diagnosis,
    posterior_update,
    prior_over_hypotheses,
    select_next_probe,
)
from knowtrace.domain.enums import AttemptContext, DiagnosisState, DiagnosisVerdict
from knowtrace.domain.errors import LessonBudgetError, NoContentError
from knowtrace.domain.lesson import assemble_lesson, recheck_passed
from knowtrace.domain.state_machine import (
    TERMINAL_STATES,
    Opened,
    ProbeObserved,
    RecheckObserved,
    SessionAbandoned,
    VerdictKind,
    diagnosis_transition,
)
from knowtrace.domain.types import SLIP, Continue, Gap, Inconclusive, ItemSpec, Slip
from knowtrace.models import Attempt, Diagnosis, DiagnosisProbe, Lesson, LessonStep
from knowtrace.repositories import diagnoses as repo
from knowtrace.repositories import learners as learner_repo
from knowtrace.services.attempts import mastery_map, record_attempt
from knowtrace.services.context import Ctx
from knowtrace.services.errors import ConflictError, NotFoundError
from knowtrace.services.views import (
    DiagnosisStepResult,
    DiagnosisView,
    HypothesisView,
    ItemView,
    ProbeView,
    TraceNodeView,
)

_LIVE = (DiagnosisState.PROBING, DiagnosisState.LESSON_ASSIGNED, DiagnosisState.RECHECKING)


def load(ctx: Ctx, diagnosis_id: str) -> Diagnosis:
    d = repo.get_diagnosis(ctx.session, diagnosis_id)
    if d is None:
        raise NotFoundError("diagnosis", diagnosis_id)
    return d


def _params(ctx: Ctx, item_id: str) -> tuple[float, float]:
    b = ctx.bundle
    return effective_item_params(b.items[item_id], [b.graph.concepts[c] for c in b.qmatrix[item_id].concepts])


def _pending_probe(d: Diagnosis) -> DiagnosisProbe | None:
    return next((p for p in reversed(d.probes) if p.attempt_id is None), None)


def _recheck_attempts(ctx: Ctx, d: Diagnosis) -> list[Attempt]:
    return [a for a in repo_attempts(ctx, d) if a.context is AttemptContext.RECHECK]


def repo_attempts(ctx: Ctx, d: Diagnosis) -> list[Attempt]:
    return list(learner_repo.attempts_for_diagnosis(ctx.session, d.id))


def _next_recheck_item(ctx: Ctx, d: Diagnosis) -> ItemSpec | None:
    """Least-used item whose primary concept is the root; deterministic tie-break by difficulty, id."""
    b, root = ctx.bundle, d.root_concept_id
    pool = [i for iid, i in b.items.items() if b.qmatrix[iid].primary == root]
    if not pool:
        return None
    used = Counter(a.item_id for a in _recheck_attempts(ctx, d))
    return min(pool, key=lambda i: (used[i.id], i.difficulty, i.id))


def _explain(ctx: Ctx, d: Diagnosis, probes_used: int) -> str:
    name = ctx.bundle.name
    match d.state:
        case DiagnosisState.PROBING:
            return f"Narrowing down the cause: question {probes_used + 1} of at most {ctx.cfg.max_probes}."
        case (
            DiagnosisState.LESSON_ASSIGNED
            | DiagnosisState.RECHECKING
            | DiagnosisState.RESOLVED
            | DiagnosisState.UNRESOLVED
        ):
            path = " -> ".join(n["name"] for n in (d.trace or []))
            conf = f"{(d.confidence or 0):.0%}"
            return f"Most likely missing: {name(d.root_concept_id or '')} (confidence {conf}). Path: {path}."
        case DiagnosisState.SLIP_DISMISSED:
            return "Your other answers show you know the prerequisites, so that miss looks like a slip."
        case DiagnosisState.INCONCLUSIVE:
            return (
                "Not enough evidence to name a single missing concept. Keep practising and we will try again."
            )
        case DiagnosisState.ABANDONED:
            return "Session ended before the diagnosis finished."


def view(ctx: Ctx, d: Diagnosis) -> DiagnosisView:
    b = ctx.bundle
    attempts = {a.id: a for a in repo_attempts(ctx, d)}
    probes = [
        ProbeView(
            p.seq,
            p.item_id,
            p.attempt_id is not None,
            attempts[p.attempt_id].is_correct if p.attempt_id in attempts else None,
            p.eig_bits,
        )
        for p in d.probes
    ]
    answered = sum(1 for p in probes if p.answered)
    pending: ItemView | None = None
    kind: AttemptContext | None = None
    if d.state is DiagnosisState.PROBING and (pp := _pending_probe(d)) is not None:
        pending, kind = b.item_view(pp.item_id), AttemptContext.PROBE
    elif d.state is DiagnosisState.RECHECKING and (nxt := _next_recheck_item(ctx, d)) is not None:
        pending, kind = b.item_view(nxt.id), AttemptContext.RECHECK
    lesson = repo.lesson_for_diagnosis(ctx.session, d.id)
    top = sorted(d.posterior.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    return DiagnosisView(
        id=d.id,
        student_id=d.student_id,
        state=d.state,
        verdict=d.verdict,
        root_concept_id=d.root_concept_id,
        root_concept_name=b.name(d.root_concept_id) if d.root_concept_id else None,
        confidence=d.confidence,
        hypotheses=[
            HypothesisView(h, "Slip (everything known)" if h == SLIP else b.name(h), p) for h, p in top
        ],
        trace=[
            TraceNodeView(n["concept_id"], n["name"], n["posterior_mass"], n["mastery"])
            for n in (d.trace or [])
        ],
        probes=probes,
        probes_used=answered,
        max_probes=ctx.cfg.max_probes,
        pending_item=pending,
        pending_kind=kind,
        lesson_id=lesson.id if lesson else None,
        rechecks_used=len(_recheck_attempts(ctx, d)),
        max_rechecks=ctx.cfg.max_rechecks,
        explanation=_explain(ctx, d, answered),
        created_at=d.created_at,
        closed_at=d.closed_at,
    )


def get_view(ctx: Ctx, diagnosis_id: str) -> DiagnosisView:
    return view(ctx, load(ctx, diagnosis_id))


def _assemble_lesson(ctx: Ctx, d: Diagnosis, root: str, trigger_item: str) -> bool:
    b = ctx.bundle
    try:
        plan = assemble_lesson(
            b.graph,
            b.atoms,
            b.items,
            b.qmatrix,
            mastery_map(ctx, d.student_id),
            root,
            list(b.qmatrix[trigger_item].concepts),
            ctx.cfg,
        )
    except (NoContentError, LessonBudgetError):
        return False
    lesson = Lesson(
        diagnosis_id=d.id, student_id=d.student_id, root_concept_id=root, est_seconds=plan.est_seconds
    )
    steps = [
        LessonStep(
            lesson_id=lesson.id,
            position=s.position,
            concept_id=s.concept_id,
            kind=s.kind,
            est_seconds=s.est_seconds,
            atom_id=s.atom_id,
            item_id=s.item_id,
        )
        for s in plan.steps
    ]
    repo.add_lesson(ctx.session, lesson, steps)
    return True


def _advance(ctx: Ctx, d: Diagnosis, post: Mapping[str, float], answered: int) -> None:
    """Decide continue / gap / slip / inconclusive and apply it (state, verdict, lesson, next probe)."""
    b, cfg = ctx.bundle, ctx.cfg
    asked = {d_trigger_item(ctx, d), *(p.item_id for p in d.probes)}
    nxt = select_next_probe(b.graph, b.items, b.qmatrix, post, asked)
    outcome = diagnosis_verdict(post, answered, cfg, probe_available=nxt is not None)
    if isinstance(outcome, Continue) and nxt is None:  # nothing left that would tell hypotheses apart
        outcome = Inconclusive(tuple(sorted(post.items(), key=lambda kv: (-kv[1], kv[0]))[:3]))
    d.posterior = dict(post)
    d.updated_at = ctx.now
    if isinstance(outcome, Continue):
        assert nxt is not None
        row = b.qmatrix[nxt.id]
        slip, guess = _params(ctx, nxt.id)
        gain = expected_information_gain(b.graph, post, row.concepts, slip, guess)
        repo.add_probe(
            ctx.session,
            DiagnosisProbe(diagnosis_id=d.id, seq=len(d.probes) + 1, item_id=nxt.id, eig_bits=gain),
        )
        d.state = diagnosis_transition(d.state, ProbeObserved(VerdictKind.CONTINUE))
    elif isinstance(outcome, Gap):
        trigger = d_trigger_item(ctx, d)
        row = b.qmatrix[trigger]
        mastery = mastery_map(ctx, d.student_id)
        d.verdict, d.root_concept_id, d.confidence = DiagnosisVerdict.GAP, outcome.concept, outcome.confidence
        for target in [row.primary, *sorted(c for c in row.concepts if c != row.primary)]:
            if target == outcome.concept or outcome.concept in b.graph.anc[target]:
                tr = explain_diagnosis(b.graph, post, mastery, target, outcome.concept)
                d.trace = [
                    {
                        "concept_id": n.concept_id,
                        "name": b.name(n.concept_id),
                        "posterior_mass": n.posterior_mass,
                        "mastery": n.mastery,
                    }
                    for n in tr.nodes
                ]
                break
        d.config_snapshot = {**d.config_snapshot, "root_mastery_at_verdict": mastery[outcome.concept]}
        assembled = _assemble_lesson(ctx, d, outcome.concept, trigger)
        d.state = diagnosis_transition(d.state, ProbeObserved(VerdictKind.GAP, lesson_assembled=assembled))
    elif isinstance(outcome, Slip):
        d.verdict, d.confidence = DiagnosisVerdict.SLIP, outcome.confidence
        d.state = diagnosis_transition(d.state, ProbeObserved(VerdictKind.SLIP))
    else:
        d.verdict = DiagnosisVerdict.INCONCLUSIVE
        d.state = diagnosis_transition(d.state, ProbeObserved(VerdictKind.INCONCLUSIVE))
    if d.state in TERMINAL_STATES:
        d.closed_at = ctx.now
    ctx.session.add(d)
    ctx.session.flush()
    ctx.session.refresh(d)


def d_trigger_item(ctx: Ctx, d: Diagnosis) -> str:
    attempt = learner_repo.get_attempt(ctx.session, d.trigger_attempt_id)
    assert attempt is not None
    return attempt.item_id


def open_for_failed_attempt(
    ctx: Ctx, student_id: str, attempt: Attempt, mastery_before: Mapping[str, float]
) -> Diagnosis:
    """Create a diagnosis for a wrong practice attempt. `mastery_before` excludes that attempt."""
    b = ctx.bundle
    open_state = diagnosis_transition(None, Opened(trigger_correct=False))
    row = b.qmatrix[attempt.item_id]
    candidates = candidate_set(b.graph, row.concepts, excluded=())
    post = prior_over_hypotheses(b.graph, mastery_before, candidates)
    slip, guess = _params(ctx, attempt.item_id)
    post = posterior_update(b.graph, post, row.concepts, slip, guess, False)  # the failure itself
    d = repo.add_diagnosis(
        ctx.session,
        Diagnosis(
            student_id=student_id,
            trigger_attempt_id=attempt.id,
            state=open_state,
            posterior=dict(post),
            config_snapshot=asdict(ctx.cfg),
            curriculum_hash=b.hash,
            created_at=ctx.now,
            updated_at=ctx.now,
        ),
    )
    attempt.diagnosis_id = d.id
    ctx.session.add(attempt)
    ctx.session.flush()
    ctx.session.refresh(d)
    _advance(ctx, d, post, 0)
    return d


def live_diagnosis(ctx: Ctx, student_id: str) -> Diagnosis | None:
    return repo.open_diagnosis(ctx.session, student_id)


def answer_probe(ctx: Ctx, diagnosis_id: str, answer: str, latency_ms: int | None) -> DiagnosisStepResult:
    d = load(ctx, diagnosis_id)
    diagnosis_transition(d.state, ProbeObserved(VerdictKind.CONTINUE))  # only legal while PROBING
    pending = _pending_probe(d)
    if pending is None:
        raise ConflictError("no probe is waiting for an answer")
    b = ctx.bundle
    attempt, attempt_view = record_attempt(
        ctx, d.student_id, pending.item_id, answer, latency_ms, AttemptContext.PROBE, diagnosis_id=d.id
    )
    row = b.qmatrix[pending.item_id]
    slip, guess = _params(ctx, pending.item_id)
    post = posterior_update(b.graph, d.posterior, row.concepts, slip, guess, attempt.is_correct)
    pending.attempt_id, pending.posterior_after = attempt.id, dict(post)
    ctx.session.add(pending)
    ctx.session.flush()
    answered = sum(1 for p in d.probes if p.attempt_id is not None)
    _advance(ctx, d, post, answered)
    ctx.commit()
    return DiagnosisStepResult(attempt_view, view(ctx, d), None, None, None)


def answer_recheck(ctx: Ctx, diagnosis_id: str, answer: str, latency_ms: int | None) -> DiagnosisStepResult:
    d = load(ctx, diagnosis_id)
    cfg = ctx.cfg
    diagnosis_transition(d.state, RecheckObserved(False, 0, cfg.max_rechecks))  # only legal while RECHECKING
    root = d.root_concept_id
    item = _next_recheck_item(ctx, d)
    if root is None or item is None:
        raise ConflictError("no recheck question is available for this diagnosis")
    _, attempt_view = record_attempt(
        ctx, d.student_id, item.id, answer, latency_ms, AttemptContext.RECHECK, diagnosis_id=d.id
    )
    history = _recheck_attempts(ctx, d)  # includes this attempt (already flushed)
    streak = 0
    for a in reversed(history):
        if not a.is_correct:
            break
        streak += 1
    p_root = attempt_view.mastery[root]
    passed = recheck_passed(p_root, streak, cfg)
    d.state = diagnosis_transition(d.state, RecheckObserved(passed, len(history), cfg.max_rechecks))
    d.updated_at = ctx.now
    if d.state in TERMINAL_STATES:
        d.closed_at = ctx.now
    ctx.session.add(d)
    ctx.session.flush()
    ctx.commit()
    before = d.config_snapshot.get("root_mastery_at_verdict")
    return DiagnosisStepResult(
        attempt_view, view(ctx, d), passed, float(before) if before is not None else None, p_root
    )


def abandon(ctx: Ctx, diagnosis_id: str) -> DiagnosisView:
    d = load(ctx, diagnosis_id)
    d.state = diagnosis_transition(d.state, SessionAbandoned())
    d.updated_at = d.closed_at = ctx.now
    ctx.session.add(d)
    ctx.commit()
    return view(ctx, d)


def list_for_student(
    ctx: Ctx, student_id: str, state: DiagnosisState | None, limit: int, offset: int
) -> list[DiagnosisView]:
    if learner_repo.get_student(ctx.session, student_id) is None:
        raise NotFoundError("student", student_id)
    return [
        view(ctx, d)
        for d in repo.page_diagnoses(ctx.session, student_id, state=state, limit=limit, offset=offset)
    ]
