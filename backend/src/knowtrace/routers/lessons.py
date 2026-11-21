from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from knowtrace.core.deps import CtxDep
from knowtrace.schemas.common import ERROR_RESPONSES
from knowtrace.schemas.diagnoses import DiagnosisOut, LessonOut, StepViewOut, StepViewRequest
from knowtrace.services import lessons as svc

router = APIRouter(prefix="/lessons", tags=["lessons"], responses=ERROR_RESPONSES)


@router.get("/{lesson_id}", summary="A micro-lesson: ordered steps, within the time budget")
def get_lesson(lesson_id: str, ctx: CtxDep) -> LessonOut:
    return LessonOut.model_validate(svc.get_lesson(ctx, lesson_id))


@router.post(
    "/{lesson_id}/steps/{position}/view", summary="Mark a step viewed (optionally answering its question)"
)
def view_step(
    lesson_id: str,
    position: Annotated[int, Path(ge=1, le=50)],
    body: StepViewRequest,
    ctx: CtxDep,
) -> StepViewOut:
    return StepViewOut.model_validate(svc.view_step(ctx, lesson_id, position, body.answer, body.latency_ms))


@router.post("/{lesson_id}/complete", summary="Finish the lesson and start the recheck")
def complete_lesson(lesson_id: str, ctx: CtxDep) -> DiagnosisOut:
    return DiagnosisOut.model_validate(svc.complete(ctx, lesson_id))
