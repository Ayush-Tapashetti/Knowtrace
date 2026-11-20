"""Diagnosis and lesson schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from knowtrace.domain.enums import AtomKind, AttemptContext, DiagnosisState, DiagnosisVerdict
from knowtrace.schemas.common import Request, Response
from knowtrace.schemas.curriculum import ItemOut


class AnswerRequest(Request):
    answer: str = Field(min_length=1, max_length=200)
    latency_ms: int | None = Field(default=None, ge=0, le=3_600_000)


class HypothesisOut(Response):
    hypothesis: str = Field(description="A concept id, or SLIP")
    name: str
    probability: float


class TraceNodeOut(Response):
    concept_id: str
    name: str
    posterior_mass: float
    mastery: float


class ProbeOut(Response):
    seq: int
    item_id: str
    answered: bool
    correct: bool | None
    eig_bits: float


class DiagnosisOut(Response):
    id: str
    student_id: str
    state: DiagnosisState
    verdict: DiagnosisVerdict | None
    root_concept_id: str | None
    root_concept_name: str | None
    confidence: float | None
    hypotheses: list[HypothesisOut]
    trace: list[TraceNodeOut] = Field(
        description="Prerequisite path from the root gap down to the failed concept"
    )
    probes: list[ProbeOut]
    probes_used: int
    max_probes: int
    pending_item: ItemOut | None = Field(
        description="The next probe or recheck question, when one is waiting"
    )
    pending_kind: AttemptContext | None
    lesson_id: str | None
    rechecks_used: int
    max_rechecks: int
    explanation: str
    created_at: datetime
    closed_at: datetime | None


class AttemptRef(Response):
    id: str
    seq: int
    item_id: str
    context: AttemptContext
    is_correct: bool
    mastery: dict[str, float]


class DiagnosisStepOut(Response):
    attempt: AttemptRef
    diagnosis: DiagnosisOut
    passed: bool | None = Field(description="Recheck answers only: whether the gap is now closed")
    root_mastery_before: float | None
    root_mastery_after: float | None


class LessonStepOut(Response):
    position: int
    concept_id: str
    concept_name: str
    kind: AtomKind
    est_seconds: int
    text: str | None
    source: Literal["authored", "model", "fallback", "cache"]
    item: ItemOut | None
    viewed: bool


class LessonOut(Response):
    id: str
    diagnosis_id: str
    root_concept_id: str
    est_seconds: int
    completed: bool
    steps: list[LessonStepOut]


class StepViewRequest(Request):
    answer: str | None = Field(
        default=None, min_length=1, max_length=200, description="For steps that carry a question"
    )
    latency_ms: int | None = Field(default=None, ge=0, le=3_600_000)


class StepViewOut(Response):
    lesson_id: str
    position: int
    viewed: bool
    attempt: AttemptRef | None
    all_viewed: bool
