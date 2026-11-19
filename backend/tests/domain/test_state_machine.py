from __future__ import annotations

import itertools

import pytest

from knowtrace.domain.enums import DiagnosisState as S
from knowtrace.domain.errors import IllegalTransitionError
from knowtrace.domain.state_machine import (
    TERMINAL_STATES,
    TRANSITIONS,
    Event,
    LessonCompleted,
    Opened,
    ProbeObserved,
    RecheckObserved,
    SessionAbandoned,
    VerdictKind,
    diagnosis_transition,
)

V = VerdictKind
ALL_EVENTS: list[Event] = [
    Opened(False), Opened(True),
    *(ProbeObserved(v, a) for v in V for a in (True, False)),
    LessonCompleted(True), LessonCompleted(False),
    RecheckObserved(True, 1, 3), RecheckObserved(False, 1, 3), RecheckObserved(False, 3, 3),
    SessionAbandoned(),
]  # fmt: skip
STATES: list[S | None] = [None, *S]

LEGAL: dict[tuple[S | None, Event], S] = {
    (None, Opened(False)): S.PROBING,
    (S.PROBING, ProbeObserved(V.CONTINUE)): S.PROBING,
    (S.PROBING, ProbeObserved(V.CONTINUE, True)): S.PROBING,  # lesson flag is irrelevant here
    (S.PROBING, ProbeObserved(V.SLIP, True)): S.SLIP_DISMISSED,
    (S.PROBING, ProbeObserved(V.INCONCLUSIVE, True)): S.INCONCLUSIVE,
    (S.PROBING, ProbeObserved(V.GAP, True)): S.LESSON_ASSIGNED,
    (S.PROBING, ProbeObserved(V.GAP, False)): S.INCONCLUSIVE,
    (S.PROBING, ProbeObserved(V.SLIP)): S.SLIP_DISMISSED,
    (S.PROBING, ProbeObserved(V.INCONCLUSIVE)): S.INCONCLUSIVE,
    (S.LESSON_ASSIGNED, LessonCompleted(True)): S.RECHECKING,
    (S.RECHECKING, RecheckObserved(True, 1, 3)): S.RESOLVED,
    (S.RECHECKING, RecheckObserved(False, 1, 3)): S.RECHECKING,
    (S.RECHECKING, RecheckObserved(False, 3, 3)): S.UNRESOLVED,
    (S.PROBING, SessionAbandoned()): S.ABANDONED,
    (S.LESSON_ASSIGNED, SessionAbandoned()): S.ABANDONED,
    (S.RECHECKING, SessionAbandoned()): S.ABANDONED,
}


def test_every_legal_transition_in_the_spec_table() -> None:
    for (state, event), expected in LEGAL.items():
        assert diagnosis_transition(state, event) is expected, (state, event)


def test_everything_else_is_illegal_exhaustively() -> None:
    checked = 0
    for state, event in itertools.product(STATES, ALL_EVENTS):
        if (state, event) in LEGAL:
            continue
        checked += 1
        with pytest.raises(IllegalTransitionError):
            diagnosis_transition(state, event)
    assert checked == len(STATES) * len(ALL_EVENTS) - len(LEGAL)


def test_terminal_states_accept_nothing() -> None:
    assert {S.RESOLVED, S.UNRESOLVED, S.SLIP_DISMISSED, S.INCONCLUSIVE, S.ABANDONED} == TERMINAL_STATES
    for state, event in itertools.product(TERMINAL_STATES, ALL_EVENTS):
        with pytest.raises(IllegalTransitionError, match="terminal"):
            diagnosis_transition(state, event)


def test_named_illegal_moves_from_the_spec() -> None:
    with pytest.raises(IllegalTransitionError):  # PROBING -> RECHECKING
        diagnosis_transition(S.PROBING, LessonCompleted(True))
    with pytest.raises(IllegalTransitionError):  # LESSON_ASSIGNED -> PROBING / RESOLVED
        diagnosis_transition(S.LESSON_ASSIGNED, ProbeObserved(V.CONTINUE))
    with pytest.raises(IllegalTransitionError):
        diagnosis_transition(S.LESSON_ASSIGNED, RecheckObserved(True, 1, 3))
    with pytest.raises(IllegalTransitionError, match="guard"):  # lesson with unviewed steps
        diagnosis_transition(S.LESSON_ASSIGNED, LessonCompleted(False))
    with pytest.raises(IllegalTransitionError, match="guard"):  # a correct attempt can't open a diagnosis
        diagnosis_transition(None, Opened(True))


def test_every_non_terminal_state_can_reach_a_terminal_one() -> None:
    reachable = {S.PROBING}
    frontier = [S.PROBING]
    while frontier:
        s = frontier.pop()
        for event in ALL_EVENTS:
            try:
                nxt = diagnosis_transition(s, event)
            except IllegalTransitionError:
                continue
            if nxt not in reachable:
                reachable.add(nxt)
                frontier.append(nxt)
    assert reachable == set(S)  # nothing unreachable, nothing stuck
    assert {k[0] for k in TRANSITIONS} == {None, S.PROBING, S.LESSON_ASSIGNED, S.RECHECKING}


def test_a_full_happy_path_and_a_retry_path() -> None:
    s = diagnosis_transition(None, Opened(False))
    s = diagnosis_transition(s, ProbeObserved(V.CONTINUE))
    s = diagnosis_transition(s, ProbeObserved(V.GAP, True))
    s = diagnosis_transition(s, LessonCompleted(True))
    s = diagnosis_transition(s, RecheckObserved(False, 1, 3))
    s = diagnosis_transition(s, RecheckObserved(False, 2, 3))
    assert diagnosis_transition(s, RecheckObserved(True, 3, 3)) is S.RESOLVED
