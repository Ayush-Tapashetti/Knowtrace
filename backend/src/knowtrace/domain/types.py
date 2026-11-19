"""Immutable value objects shared across the pure domain layer. Standard library only."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from knowtrace.domain.enums import AtomKind, ItemKind

ConceptId = str
Prob = float

# Hypothesis id for "everything is mastered; the failure was a slip". Reserved: no concept may use it.
SLIP = "SLIP"


@dataclass(frozen=True, slots=True)
class ConceptSpec:
    id: str
    tier: int
    p_init: float
    p_learn: float
    p_slip: float
    p_guess: float
    p_forget: float
    half_life_days: float
    name: str = ""


@dataclass(frozen=True, slots=True)
class ItemSpec:
    id: str
    kind: ItemKind
    answer: str
    choices: tuple[str, ...] = ()  # choice ids (MCQ only)
    tolerance_abs: float | None = None
    tolerance_rel: float | None = None
    difficulty: float = 0.5
    p_slip: float | None = None
    p_guess: float | None = None


@dataclass(frozen=True, slots=True)
class QRow:
    """Q-matrix row for one item: every concept required, and the one primary concept."""

    concepts: tuple[str, ...]
    primary: str


@dataclass(frozen=True, slots=True)
class AtomSpec:
    id: str
    concept_id: str
    kind: AtomKind
    est_seconds: int
    order_hint: int = 0
    item_id: str | None = None
    body: str = ""


@dataclass(frozen=True, eq=False)
class Graph:
    """Validated prerequisite DAG with precomputed closures (built by `validate_graph`)."""

    concepts: Mapping[str, ConceptSpec]
    parents: Mapping[str, tuple[str, ...]]  # direct prerequisites, sorted
    children: Mapping[str, tuple[str, ...]]  # direct dependents, sorted
    order: tuple[str, ...]  # topological: prerequisites first, ties by (tier, id)
    anc: Mapping[str, frozenset[str]]  # transitive prerequisites (excludes self)
    desc: Mapping[str, frozenset[str]]  # transitive dependents (excludes self)


@dataclass(frozen=True, slots=True)
class Observation:
    """One graded attempt, as needed to replay mastery."""

    seq: int
    item_id: str
    correct: bool


# --- Diagnosis outcomes -------------------------------------------------------------------------
Ranked = tuple[tuple[str, float], ...]


@dataclass(frozen=True, slots=True)
class Continue:
    pass


@dataclass(frozen=True, slots=True)
class Gap:
    concept: str
    confidence: float
    ranked: Ranked


@dataclass(frozen=True, slots=True)
class Slip:
    confidence: float


@dataclass(frozen=True, slots=True)
class Inconclusive:
    ranked: Ranked


DiagnosisOutcome = Continue | Gap | Slip | Inconclusive


@dataclass(frozen=True, slots=True)
class TraceNode:
    concept_id: str
    posterior_mass: float
    mastery: float


@dataclass(frozen=True, slots=True)
class Trace:
    """Prerequisite path from the diagnosed root down to the concept that failed."""

    nodes: tuple[TraceNode, ...]


@dataclass(frozen=True, slots=True)
class ProbeRecord:
    seq: int
    item_id: str
    correct: bool
    eig_bits: float
    posterior_after: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class EpisodeResult:
    outcome: DiagnosisOutcome
    probes: tuple[ProbeRecord, ...]
    posterior: Mapping[str, float]
    trace: Trace | None


# --- Lessons ------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class LessonStepPlan:
    position: int
    concept_id: str
    kind: AtomKind
    est_seconds: int
    atom_id: str | None = None  # None only for item-bank fallback steps
    item_id: str | None = None


@dataclass(frozen=True, slots=True)
class LessonPlan:
    root: str
    steps: tuple[LessonStepPlan, ...]
    est_seconds: int


@dataclass(frozen=True, slots=True)
class ReliabilityBin:
    p_pred_mean: float
    p_obs_mean: float
    count: int
