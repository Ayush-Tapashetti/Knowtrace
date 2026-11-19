from __future__ import annotations

import itertools
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from knowtrace.domain.bkt import (
    apply_time_forgetting,
    bkt_posterior,
    bkt_transition,
    clamp_prob,
    effective_item_params,
    item_success_probability,
    multi_concept_evidence,
    replay_attempts,
    update_mastery_from_attempt,
)
from knowtrace.domain.enums import ItemKind
from knowtrace.domain.errors import (
    InvalidParameterError,
    InvalidProbabilityError,
    QMatrixError,
    UnknownConceptError,
)
from knowtrace.domain.types import ItemSpec, Observation, QRow
from tests.domain.fixture import concept, mcq

prob = st.floats(0.01, 0.99)


def test_clamp_prob() -> None:
    assert clamp_prob(0.0) == 1e-6 and clamp_prob(1.0) == 1 - 1e-6 and clamp_prob(0.5) == 0.5
    with pytest.raises(InvalidProbabilityError):
        clamp_prob(float("nan"))


def test_hand_computed_update_matches_to_1e9() -> None:
    # p=0.3, slip=0.1, guess=0.2, learn=0.15, forget=0.02, answer correct
    p, s, g, learn, forget = (Fraction(x) for x in ("0.3", "0.1", "0.2", "0.15", "0.02"))
    post = p * (1 - s) / (p * (1 - s) + (1 - p) * g)  # 27/41
    expected = post * (1 - forget) + (1 - post) * learn
    got_post = bkt_posterior(0.3, True, 0.1, 0.2)
    assert got_post == pytest.approx(float(post), abs=1e-9)
    assert bkt_transition(got_post, 0.15, 0.02) == pytest.approx(float(expected), abs=1e-9)

    # and the wrong-answer branch
    wrong = p * s / (p * s + (1 - p) * (1 - g))
    assert bkt_posterior(0.3, False, 0.1, 0.2) == pytest.approx(float(wrong), abs=1e-9)


def test_effective_params_precedence() -> None:
    cs = [concept("A", p_slip=0.1, p_guess=0.2), concept("B", p_slip=0.3, p_guess=0.4)]
    assert effective_item_params(mcq("q", p_slip=0.05, p_guess=0.07), cs) == (0.05, 0.07)  # item overrides
    assert effective_item_params(mcq("q"), cs) == (pytest.approx(0.2), 0.25)  # mean slip, MCQ guess = 1/4
    num = ItemSpec("n", ItemKind.NUMERIC, "1")
    assert effective_item_params(num, cs) == (pytest.approx(0.2), pytest.approx(0.3))  # concept means
    with pytest.raises(QMatrixError):
        effective_item_params(num, [])


@given(prob, st.booleans(), st.floats(0.01, 0.4), st.floats(0.01, 0.4))
def test_evidence_step_moves_with_the_answer(p: float, correct: bool, slip: float, guess: float) -> None:
    post = bkt_posterior(p, correct, slip, guess)
    assert 0 < post < 1
    # slip + guess < 1 here, so a correct answer is evidence *for* mastery and a wrong one against
    assert (post >= p) if correct else (post <= p)
    assert bkt_posterior(p, True, slip, guess) >= bkt_posterior(p, False, slip, guess)


@given(prob, prob, prob)
def test_transition_stays_in_range(p: float, learn: float, forget: float) -> None:
    assert 0 < bkt_transition(p, learn, forget) < 1


def test_time_forgetting() -> None:
    assert apply_time_forgetting(0.9, 0, 14, 0.2) == pytest.approx(0.9)
    assert apply_time_forgetting(0.9, 14, 14, 0.2) == pytest.approx(0.2 + 0.7 / 2)  # one half-life
    assert apply_time_forgetting(0.9, -5, 14, 0.2) == pytest.approx(0.9)  # negative time is treated as 0
    assert apply_time_forgetting(0.9, 1e6, 14, 0.2) == pytest.approx(0.2, abs=1e-6)
    with pytest.raises(InvalidParameterError):
        apply_time_forgetting(0.9, 1, 0, 0.2)


def test_noisy_and_success_probability() -> None:
    m = {"A": 0.8, "B": 0.5}
    # prod = 0.4: 0.4*0.9 + 0.6*0.2 = 0.48
    assert item_success_probability(["A", "B"], m, 0.1, 0.2) == pytest.approx(0.48)
    with pytest.raises(UnknownConceptError):
        item_success_probability(["Z"], m, 0.1, 0.2)


@given(st.lists(prob, min_size=1, max_size=4), st.booleans(), st.floats(0.01, 0.4), st.floats(0.01, 0.4))
def test_multi_concept_evidence_equals_brute_force_joint(
    ps: list[float], correct: bool, slip: float, guess: float
) -> None:
    ids = [f"c{i}" for i in range(len(ps))]
    mastery = dict(zip(ids, ps, strict=True))
    got = multi_concept_evidence(mastery, ids, slip, guess, correct)
    # enumerate all 2^n true states with independent priors
    num = dict.fromkeys(ids, 0.0)
    den = 0.0
    for state in itertools.product([True, False], repeat=len(ids)):
        w = 1.0
        for p, s in zip(ps, state, strict=True):
            w *= p if s else 1 - p
        p_ok = (1 - slip) if all(state) else guess
        like = w * (p_ok if correct else 1 - p_ok)
        den += like
        for cid, s in zip(ids, state, strict=True):
            if s:
                num[cid] += like
    for cid in ids:
        assert got[cid] == pytest.approx(num[cid] / den, abs=1e-9)


def test_single_concept_update_reduces_to_plain_bkt() -> None:
    specs = {"A": concept("A")}
    item = mcq("q", p_slip=0.1, p_guess=0.2)
    out = update_mastery_from_attempt({"A": 0.3, "B": 0.6}, item, ["A"], specs, True)
    assert out["A"] == pytest.approx(bkt_transition(bkt_posterior(0.3, True, 0.1, 0.2), 0.15, 0.02))
    assert out["B"] == 0.6  # concepts outside the item are untouched


@given(st.lists(prob, min_size=1, max_size=3), st.booleans())
def test_update_is_bounded_and_correct_beats_wrong(ps: list[float], _: bool) -> None:
    ids = [f"c{i}" for i in range(len(ps))]
    specs = {c: concept(c) for c in ids}
    mastery = dict(zip(ids, ps, strict=True))
    item = mcq("q", p_slip=0.1, p_guess=0.2)
    ok = update_mastery_from_attempt(mastery, item, ids, specs, True)
    bad = update_mastery_from_attempt(mastery, item, ids, specs, False)
    for c in ids:
        assert 0 < bad[c] < ok[c] < 1  # same prior: a correct answer always ends above a wrong one


def test_replay_matches_incremental_updates() -> None:
    ids = ["A", "B"]
    specs = {c: concept(c) for c in ids}
    items = {"q1": mcq("q1"), "q2": mcq("q2")}
    q = {"q1": QRow(("A",), "A"), "q2": QRow(("A", "B"), "B")}
    init = {"A": 0.3, "B": 0.3}
    seq = [True, False, True, True]
    obs = [Observation(i + 1, "q1" if i % 2 == 0 else "q2", c) for i, c in enumerate(seq)]

    inc = dict(init)
    for o in obs:
        inc = update_mastery_from_attempt(inc, items[o.item_id], q[o.item_id].concepts, specs, o.correct)
    assert replay_attempts(init, list(reversed(obs)), items, q, specs) == inc  # order given doesn't matter
    with pytest.raises(QMatrixError):
        replay_attempts(init, [Observation(1, "nope", True)], items, q, specs)
