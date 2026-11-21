from __future__ import annotations

from fastapi import APIRouter

from knowtrace.core.deps import CtxDep
from knowtrace.schemas.common import ERROR_RESPONSES
from knowtrace.schemas.diagnoses import AnswerRequest, DiagnosisOut, DiagnosisStepOut
from knowtrace.services import diagnoses as svc

router = APIRouter(prefix="/diagnoses", tags=["diagnoses"], responses=ERROR_RESPONSES)


@router.get("/{diagnosis_id}", summary="Current state of a diagnosis, with trace and the next question")
def get_diagnosis(diagnosis_id: str, ctx: CtxDep) -> DiagnosisOut:
    return DiagnosisOut.model_validate(svc.get_view(ctx, diagnosis_id))


@router.post("/{diagnosis_id}/answer", summary="Answer the pending diagnostic probe")
def answer_probe(diagnosis_id: str, body: AnswerRequest, ctx: CtxDep) -> DiagnosisStepOut:
    return DiagnosisStepOut.model_validate(svc.answer_probe(ctx, diagnosis_id, body.answer, body.latency_ms))


@router.post("/{diagnosis_id}/recheck", summary="Answer the post-lesson recheck question")
def answer_recheck(diagnosis_id: str, body: AnswerRequest, ctx: CtxDep) -> DiagnosisStepOut:
    return DiagnosisStepOut.model_validate(
        svc.answer_recheck(ctx, diagnosis_id, body.answer, body.latency_ms)
    )


@router.post("/{diagnosis_id}/abandon", summary="End an unfinished diagnosis")
def abandon_diagnosis(diagnosis_id: str, ctx: CtxDep) -> DiagnosisOut:
    return DiagnosisOut.model_validate(svc.abandon(ctx, diagnosis_id))
