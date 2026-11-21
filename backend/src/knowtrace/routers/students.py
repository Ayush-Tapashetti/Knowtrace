from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from knowtrace.core.deps import CtxDep
from knowtrace.domain.enums import DiagnosisState
from knowtrace.schemas.common import ERROR_RESPONSES, Limit, Offset
from knowtrace.schemas.diagnoses import DiagnosisOut
from knowtrace.schemas.students import (
    AttemptCreate,
    AttemptResultOut,
    ForecastOut,
    MasteryOut,
    StudentCreate,
    StudentOut,
)
from knowtrace.services import diagnoses as diagnosis_svc
from knowtrace.services import learners as svc

router = APIRouter(prefix="/students", tags=["students"], responses=ERROR_RESPONSES)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a pseudonymous student")
def create_student(body: StudentCreate, ctx: CtxDep) -> StudentOut:
    return StudentOut.model_validate(svc.create_student(ctx, body.pseudonym))


@router.get("/{student_id}", summary="Get a student")
def get_student(student_id: str, ctx: CtxDep) -> StudentOut:
    return StudentOut.model_validate(svc.get_student(ctx, student_id))


@router.get("/{student_id}/mastery", summary="Knowledge state: mastery per concept (heatmap data)")
def get_mastery(student_id: str, ctx: CtxDep) -> MasteryOut:
    return MasteryOut.model_validate(svc.mastery_view(ctx, student_id))


@router.get("/{student_id}/forecast", summary="Mastery trajectory with uncertainty band")
def get_forecast(
    student_id: str,
    ctx: CtxDep,
    concept_id: Annotated[str, Query(min_length=1, max_length=100)],
    horizon: Annotated[int, Query(ge=1, le=svc.MAX_HORIZON, description="Future attempts to project")] = 20,
) -> ForecastOut:
    return ForecastOut.model_validate(svc.forecast_view(ctx, student_id, concept_id, horizon))


@router.post(
    "/{student_id}/attempts",
    status_code=status.HTTP_201_CREATED,
    summary="Answer a practice item; a wrong answer opens a diagnosis",
)
def submit_attempt(student_id: str, body: AttemptCreate, ctx: CtxDep) -> AttemptResultOut:
    return AttemptResultOut.model_validate(
        svc.submit_practice(ctx, student_id, body.item_id, body.answer, body.latency_ms)
    )


@router.get("/{student_id}/diagnoses", summary="A student's diagnoses, newest first")
def list_diagnoses(
    student_id: str,
    ctx: CtxDep,
    limit: Limit = 20,
    offset: Offset = 0,
    state: DiagnosisState | None = None,
) -> list[DiagnosisOut]:
    rows = diagnosis_svc.list_for_student(ctx, student_id, state, limit, offset)
    return [DiagnosisOut.model_validate(r) for r in rows]
