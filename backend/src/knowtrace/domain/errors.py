"""Named domain errors. Routers map these to HTTP codes in one place (never here)."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for every error the pure domain layer raises on purpose."""


class GraphCycleError(DomainError):
    def __init__(self, path: list[str]) -> None:
        super().__init__("prerequisite cycle: " + " -> ".join(path))
        self.path = path


class GraphStructureError(DomainError):
    """Duplicate concept/edge or a reserved id (e.g. `SLIP`)."""


class UnknownConceptError(DomainError):
    def __init__(self, concept_id: str) -> None:
        super().__init__(f"unknown concept: {concept_id!r}")
        self.concept_id = concept_id


class QMatrixError(DomainError):
    """Item/Q-matrix content is inconsistent."""


class InvalidAnswerError(DomainError):
    """The learner's answer is malformed (not an unknown-but-wrong answer)."""


class InvalidProbabilityError(DomainError):
    """A probability was NaN or otherwise unusable."""


class InvalidParameterError(DomainError):
    """A numeric parameter is outside its allowed range."""


class IllegalTransitionError(DomainError):
    def __init__(self, state: object, event: object, reason: str = "") -> None:
        msg = f"illegal transition from {state!r} on {type(event).__name__}"
        super().__init__(f"{msg}: {reason}" if reason else msg)
        self.state = state
        self.event = event


class EmptyCandidateSetError(DomainError):
    """Nothing is left to diagnose (everything required was excluded)."""


class NoPathError(DomainError):
    """No prerequisite path exists between two concepts."""


class NoContentError(DomainError):
    def __init__(self, concept_id: str) -> None:
        super().__init__(f"no lesson content (atoms or items) for concept {concept_id!r}")
        self.concept_id = concept_id


class LessonBudgetError(DomainError):
    """Required lesson steps alone exceed the time budget."""
