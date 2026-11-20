"""Plain result objects returned by services. Routers turn them into response schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Generic, TypeVar

from knowtrace.domain.enums import AtomKind, AttemptContext, DiagnosisState, DiagnosisVerdict, ItemKind


@dataclass(frozen=True)
class ChoiceView:
    id: str
    text: str


@dataclass(frozen=True)
class ItemView:
    """An item as shown to a learner. Never carries the answer key."""

    id: str
    stem: str
    kind: ItemKind
    choices: list[ChoiceView]
    concept_ids: list[str]
    primary_concept_id: str
    difficulty: float


@dataclass(frozen=True)
class ConceptView:
    id: str
    name: str
    description: str
    strand: str
    tier: int
    prerequisites: list[str]


@dataclass(frozen=True)
class ConceptDetailView(ConceptView):
    dependents: list[str] = field(default_factory=list)
    ancestors: dict[str, int] = field(default_factory=dict)  # transitive prerequisite -> distance
    item_count: int = 0


@dataclass(frozen=True)
class EdgeView:
    prerequisite: str
    dependent: str


@dataclass(frozen=True)
class GraphView:
    curriculum_hash: str
    nodes: list[ConceptView]
    edges: list[EdgeView]


T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class StudentView:
    id: str
    pseudonym: str
    created_at: datetime


@dataclass(frozen=True)
class MasteryPoint:
    concept_id: str
    name: str
    p_mastery: float
    n_obs: int
    mastered: bool
    last_observed_at: datetime | None


@dataclass(frozen=True)
class MasteryView:
    student_id: str
    theta_master: float
    concepts: list[MasteryPoint]


@dataclass(frozen=True)
class TraceNodeView:
    concept_id: str
    name: str
    posterior_mass: float
    mastery: float


@dataclass(frozen=True)
class HypothesisView:
    hypothesis: str  # concept id or "SLIP"
    name: str
    probability: float


@dataclass(frozen=True)
class ProbeView:
    seq: int
    item_id: str
    answered: bool
    correct: bool | None
    eig_bits: float


@dataclass(frozen=True)
class LessonStepView:
    position: int
    concept_id: str
    concept_name: str
    kind: AtomKind
    est_seconds: int
    text: str | None
    source: str  # authored | model | fallback | cache
    item: ItemView | None
    viewed: bool


@dataclass(frozen=True)
class LessonView:
    id: str
    diagnosis_id: str
    root_concept_id: str
    est_seconds: int
    completed: bool
    steps: list[LessonStepView]


@dataclass(frozen=True)
class DiagnosisView:
    id: str
    student_id: str
    state: DiagnosisState
    verdict: DiagnosisVerdict | None
    root_concept_id: str | None
    root_concept_name: str | None
    confidence: float | None
    hypotheses: list[HypothesisView]
    trace: list[TraceNodeView]
    probes: list[ProbeView]
    probes_used: int
    max_probes: int
    pending_item: ItemView | None  # next probe or recheck question to answer
    pending_kind: AttemptContext | None
    lesson_id: str | None
    rechecks_used: int
    max_rechecks: int
    explanation: str
    created_at: datetime
    closed_at: datetime | None


@dataclass(frozen=True)
class AttemptView:
    id: str
    seq: int
    item_id: str
    context: AttemptContext
    is_correct: bool
    mastery: dict[str, float]  # concept id -> p_mastery after this attempt (concepts touched)


@dataclass(frozen=True)
class AttemptResult:
    attempt: AttemptView
    diagnosis: DiagnosisView | None  # opened when a practice attempt is wrong


@dataclass(frozen=True)
class StepViewResult:
    lesson_id: str
    position: int
    viewed: bool
    attempt: AttemptView | None
    all_viewed: bool


@dataclass(frozen=True)
class DiagnosisStepResult:
    attempt: AttemptView
    diagnosis: DiagnosisView
    passed: bool | None  # set on recheck answers
    root_mastery_before: float | None
    root_mastery_after: float | None


@dataclass(frozen=True)
class ForecastPoint:
    step: int
    p_mastery: float
    p_lo: float
    p_hi: float


@dataclass(frozen=True)
class ForecastView:
    student_id: str
    concept_id: str
    concept_name: str
    current_mastery: float
    theta_master: float
    points: list[ForecastPoint]
    steps_to_mastery: int | None
    p_next_correct: float


@dataclass(frozen=True)
class EvalMetric:
    method: str
    metric: str
    value: float
    n: int
    detail: dict[str, object] | None


@dataclass(frozen=True)
class EvalView:
    run_id: str
    created_at: datetime
    seed: int
    n_students: int
    curriculum_hash: str
    metrics: list[EvalMetric]


@dataclass(frozen=True)
class StatusView:
    status: str  # ok | degraded
    app_env: str
    database_ok: bool
    curriculum_loaded: bool
    curriculum_hash: str | None
    counts: dict[str, int]
    llm_mode: str  # deterministic | model
    fallback_active: bool
    llm_model: str | None
