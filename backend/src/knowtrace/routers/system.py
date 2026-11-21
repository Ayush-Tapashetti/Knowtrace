from __future__ import annotations

from fastapi import APIRouter

from knowtrace.core.deps import CtxDep
from knowtrace.schemas.common import ERROR_RESPONSES
from knowtrace.schemas.system import EvalOut, HealthOut, StatusOut
from knowtrace.services import evaluation, status

router = APIRouter(tags=["system"], responses=ERROR_RESPONSES)


@router.get("/health", summary="Liveness: the process is up")
def health() -> HealthOut:
    return HealthOut(status="ok")


@router.get("/status", summary="Readiness: database, curriculum, and whether the optional model is in use")
def get_status(ctx: CtxDep) -> StatusOut:
    return StatusOut.model_validate(status.status(ctx))


@router.get("/eval/latest", summary="Latest evaluation run (accuracy vs baselines, forecast calibration)")
def latest_eval(ctx: CtxDep) -> EvalOut:
    return EvalOut.model_validate(evaluation.latest(ctx))
