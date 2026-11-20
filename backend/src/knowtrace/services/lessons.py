"""Serving a lesson, tracking which steps were viewed, and finishing it."""

from __future__ import annotations

from knowtrace.domain.enums import AtomKind, AttemptContext, DiagnosisState
from knowtrace.domain.state_machine import LessonCompleted, diagnosis_transition
from knowtrace.models import Lesson, LessonStep
from knowtrace.repositories import diagnoses as repo
from knowtrace.services import diagnoses
from knowtrace.services.attempts import record_attempt
from knowtrace.services.context import Ctx
from knowtrace.services.errors import BadRequestError, ConflictError, NotFoundError
from knowtrace.services.views import DiagnosisView, LessonStepView, LessonView, StepViewResult

_REPHRASABLE = (AtomKind.DEFINITION, AtomKind.WORKED_EXAMPLE, AtomKind.BRIDGE)


def _load(ctx: Ctx, lesson_id: str) -> tuple[Lesson, list[LessonStep]]:
    lesson = repo.get_lesson(ctx.session, lesson_id)
    if lesson is None:
        raise NotFoundError("lesson", lesson_id)
    return lesson, list(repo.steps_for_lesson(ctx.session, lesson_id))


def _step_view(ctx: Ctx, step: LessonStep, lesson_concepts: list[str]) -> LessonStepView:
    b = ctx.bundle
    text = b.atom_body(step.atom_id) if step.atom_id else None
    source = "authored"
    if text and step.kind in _REPHRASABLE and ctx.rephraser is not None:
        res = ctx.rephraser.rephrase(text, step.concept_id, lesson_concepts)
        text = res.text
        source = "authored" if res.reason == "disabled" else res.source
    return LessonStepView(
        position=step.position,
        concept_id=step.concept_id,
        concept_name=b.name(step.concept_id),
        kind=step.kind,
        est_seconds=step.est_seconds,
        text=text or None,
        source=source,
        item=b.item_view(step.item_id) if step.item_id else None,
        viewed=step.viewed_at is not None,
    )


def get_lesson(ctx: Ctx, lesson_id: str) -> LessonView:
    lesson, steps = _load(ctx, lesson_id)
    concepts = sorted({s.concept_id for s in steps})
    return LessonView(
        id=lesson.id,
        diagnosis_id=lesson.diagnosis_id,
        root_concept_id=lesson.root_concept_id,
        est_seconds=lesson.est_seconds,
        completed=lesson.completed_at is not None,
        steps=[_step_view(ctx, s, concepts) for s in steps],
    )


def view_step(
    ctx: Ctx, lesson_id: str, position: int, answer: str | None, latency_ms: int | None
) -> StepViewResult:
    lesson, steps = _load(ctx, lesson_id)
    d = diagnoses.load(ctx, lesson.diagnosis_id)
    if d.state is not DiagnosisState.LESSON_ASSIGNED:
        raise ConflictError("this lesson is not open", details={"state": d.state.value})
    step = next((s for s in steps if s.position == position), None)
    if step is None:
        raise NotFoundError("lesson step", str(position))
    attempt_view = None
    if answer is not None:
        if step.item_id is None:
            raise BadRequestError("this step has no question to answer")
        _, attempt_view = record_attempt(
            ctx,
            lesson.student_id,
            step.item_id,
            answer,
            latency_ms,
            AttemptContext.LESSON_CHECK,
            diagnosis_id=d.id,
        )
    if step.viewed_at is None:
        step.viewed_at = ctx.now
        ctx.session.add(step)
    ctx.commit()
    return StepViewResult(
        lesson.id, position, True, attempt_view, all(s.viewed_at is not None for s in steps)
    )


def complete(ctx: Ctx, lesson_id: str) -> DiagnosisView:
    lesson, steps = _load(ctx, lesson_id)
    d = diagnoses.load(ctx, lesson.diagnosis_id)
    d.state = diagnosis_transition(d.state, LessonCompleted(all(s.viewed_at is not None for s in steps)))
    d.updated_at = lesson.completed_at = ctx.now
    ctx.session.add_all([d, lesson])
    ctx.commit()
    return diagnoses.view(ctx, d)
