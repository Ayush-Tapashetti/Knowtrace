"""Health, status and evaluation schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from knowtrace.schemas.common import Response


class HealthOut(Response):
    status: Literal["ok"]


class StatusOut(Response):
    status: Literal["ok", "degraded"]
    app_env: str
    database_ok: bool
    curriculum_loaded: bool
    curriculum_hash: str | None
    counts: dict[str, int]
    llm_mode: Literal["deterministic", "model"]
    fallback_active: bool
    llm_model: str | None


class EvalMetricOut(Response):
    method: str
    metric: str
    value: float
    n: int
    detail: dict[str, Any] | None


class EvalOut(Response):
    run_id: str
    created_at: datetime
    seed: int
    n_students: int
    curriculum_hash: str
    metrics: list[EvalMetricOut]
