"""Shared vocabulary used by both the pure domain layer and the persistence models.

Standard library only. Values equal names so the DB stores readable strings.
"""

from enum import StrEnum


class ItemKind(StrEnum):
    MCQ = "MCQ"
    NUMERIC = "NUMERIC"


class AtomKind(StrEnum):
    DEFINITION = "DEFINITION"
    WORKED_EXAMPLE = "WORKED_EXAMPLE"
    BRIDGE = "BRIDGE"
    PRACTICE = "PRACTICE"
    CHECK = "CHECK"


class AttemptContext(StrEnum):
    PRACTICE = "PRACTICE"
    PROBE = "PROBE"
    LESSON_CHECK = "LESSON_CHECK"
    RECHECK = "RECHECK"


class DiagnosisState(StrEnum):
    PROBING = "PROBING"
    LESSON_ASSIGNED = "LESSON_ASSIGNED"
    RECHECKING = "RECHECKING"
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    SLIP_DISMISSED = "SLIP_DISMISSED"
    INCONCLUSIVE = "INCONCLUSIVE"
    ABANDONED = "ABANDONED"


class DiagnosisVerdict(StrEnum):
    GAP = "GAP"
    SLIP = "SLIP"
    INCONCLUSIVE = "INCONCLUSIVE"
