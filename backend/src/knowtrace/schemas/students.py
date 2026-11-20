"""Student, attempt, mastery and forecast schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from knowtrace.schemas.common import Request, Response
from knowtrace.schemas.diagnoses import AttemptRef, DiagnosisOut


class StudentCreate(Request):
    pseudonym: str | None = Field(
        default=None,
        min_length=3,
        max_length=40,
        pattern=r"^[A-Za-z0-9_.-]+$",
        description="Optional pseudonym. Do not use a real name; one is generated when omitted.",
    )


class StudentOut(Response):
    id: str
    pseudonym: str
    created_at: datetime


class AttemptCreate(Request):
    item_id: str = Field(min_length=1, max_length=100)
    answer: str = Field(min_length=1, max_length=200)
    latency_ms: int | None = Field(default=None, ge=0, le=3_600_000)


class AttemptResultOut(Response):
    attempt: AttemptRef
    diagnosis: DiagnosisOut | None = Field(
        description="Present when a wrong practice answer opened a diagnosis"
    )


class MasteryPointOut(Response):
    concept_id: str
    name: str
    p_mastery: float
    n_obs: int
    mastered: bool
    last_observed_at: datetime | None


class MasteryOut(Response):
    student_id: str
    theta_master: float
    concepts: list[MasteryPointOut]


class ForecastPointOut(Response):
    step: int
    p_mastery: float
    p_lo: float
    p_hi: float


class ForecastOut(Response):
    student_id: str
    concept_id: str
    concept_name: str
    current_mastery: float
    theta_master: float
    points: list[ForecastPointOut]
    steps_to_mastery: int | None = Field(
        description="Attempts until mastery is expected; null if not within 60"
    )
    p_next_correct: float
