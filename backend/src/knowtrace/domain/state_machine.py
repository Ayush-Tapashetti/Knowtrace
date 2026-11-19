"""Diagnosis lifecycle as a transition table plus one pure `diagnosis_transition` function."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from knowtrace.domain.enums import DiagnosisState as S
from knowtrace.domain.errors import IllegalTransitionError


class VerdictKind(StrEnum):
    CONTINUE = "CONTINUE"
    GAP = "GAP"
    SLIP = "SLIP"
    INCONCLUSIVE = "INCONCLUSIVE"


# Events carry the precomputed guard facts, so the transition function never reads a DB or clock.
@dataclass(frozen=True, slots=True)
class Opened:
    trigger_correct: bool


@dataclass(frozen=True, slots=True)
class ProbeObserved:
    verdict_kind: VerdictKind
    lesson_assembled: bool = False


@dataclass(frozen=True, slots=True)
class LessonCompleted:
    all_steps_viewed: bool


@dataclass(frozen=True, slots=True)
class RecheckObserved:
    passed: bool
    rechecks_used: int  # including this one
    max_rechecks: int


@dataclass(frozen=True, slots=True)
class SessionAbandoned:
    pass


Event = Opened | ProbeObserved | LessonCompleted | RecheckObserved | SessionAbandoned

TERMINAL_STATES: frozenset[S] = frozenset(
    {S.RESOLVED, S.UNRESOLVED, S.SLIP_DISMISSED, S.INCONCLUSIVE, S.ABANDONED}
)
_ABANDONABLE: tuple[S, ...] = (S.PROBING, S.LESSON_ASSIGNED, S.RECHECKING)

# A resolver returns the next state, or None when its guard rejects the event.
_Resolver = Callable[[Event], S | None]


def _opened(e: Event) -> S | None:
    assert isinstance(e, Opened)
    return S.PROBING if not e.trigger_correct else None


def _probed(e: Event) -> S | None:
    assert isinstance(e, ProbeObserved)
    match e.verdict_kind:
        case VerdictKind.CONTINUE:
            return S.PROBING
        case VerdictKind.GAP:
            return S.LESSON_ASSIGNED if e.lesson_assembled else S.INCONCLUSIVE
        case VerdictKind.SLIP:
            return S.SLIP_DISMISSED
        case VerdictKind.INCONCLUSIVE:
            return S.INCONCLUSIVE


def _lesson_done(e: Event) -> S | None:
    assert isinstance(e, LessonCompleted)
    return S.RECHECKING if e.all_steps_viewed else None


def _rechecked(e: Event) -> S | None:
    assert isinstance(e, RecheckObserved)
    if e.passed:
        return S.RESOLVED
    return S.RECHECKING if e.rechecks_used < e.max_rechecks else S.UNRESOLVED


def _abandoned(e: Event) -> S | None:
    assert isinstance(e, SessionAbandoned)
    return S.ABANDONED


TRANSITIONS: dict[tuple[S | None, type[Event]], _Resolver] = {
    (None, Opened): _opened,
    (S.PROBING, ProbeObserved): _probed,
    (S.LESSON_ASSIGNED, LessonCompleted): _lesson_done,
    (S.RECHECKING, RecheckObserved): _rechecked,
    **{(s, SessionAbandoned): _abandoned for s in _ABANDONABLE},
}


def diagnosis_transition(state: S | None, event: Event) -> S:
    """Pure `(state, event) -> new_state`. `state=None` means the diagnosis does not exist yet.

    Raises `IllegalTransitionError` for any pair not in `TRANSITIONS` and for guard failures
    (opening on a correct attempt, completing a lesson with unviewed steps).
    """
    resolver = TRANSITIONS.get((state, type(event)))
    if resolver is None:
        reason = "terminal state" if state in TERMINAL_STATES else "no such transition"
        raise IllegalTransitionError(state, event, reason)
    nxt = resolver(event)
    if nxt is None:
        raise IllegalTransitionError(state, event, "guard not satisfied")
    return nxt
