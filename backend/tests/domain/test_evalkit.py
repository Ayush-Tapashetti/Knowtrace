from __future__ import annotations

import random

import pytest

from knowtrace.domain.errors import InvalidParameterError, UnknownConceptError
from knowtrace.domain.evalkit import (
    auc,
    baseline_blame_parent,
    baseline_flat_bkt_predict,
    brier_score,
    flat_bkt_update,
    generate_true_state,
    reliability_bins,
    simulate_response,
    top_k_accuracy,
)
from tests.domain.fixture import build, concept

CUR = build()
G = CUR.graph


def test_true_state_breaks_gaps_and_everything_downstream() -> None:
    ts = generate_true_state(G, ["C"])
    assert ts == {"A": True, "B": True, "C": False, "D": False, "E": True, "F": False}
    assert all(generate_true_state(G, []).values())
    assert generate_true_state(G, ["B", "C"]) == generate_true_state(G, ["B"])  # downstream gap is implied
    with pytest.raises(UnknownConceptError):
        generate_true_state(G, ["Z"])


def test_simulated_responses_follow_slip_and_guess() -> None:
    specs = G.concepts
    item = CUR.items["i.F.1"]  # slip 0.1 (concept mean), guess 0.1 (item override)
    mastered = generate_true_state(G, [])
    broken = generate_true_state(G, ["B"])
    n = 20_000
    rng = random.Random(7)
    hits_m = sum(simulate_response(item, ["F"], specs, mastered, rng) for _ in range(n)) / n
    hits_b = sum(simulate_response(item, ["F"], specs, broken, rng) for _ in range(n)) / n
    assert hits_m == pytest.approx(0.9, abs=0.01) and hits_b == pytest.approx(0.1, abs=0.01)
    over = [simulate_response(item, ["F"], specs, mastered, random.Random(1), slip=0.5) for _ in range(1)]
    assert over == [random.Random(1).random() < 0.5]  # overrides replace the model's own slip


def test_simulation_is_reproducible_from_the_seed() -> None:
    def run() -> list[bool]:
        rng = random.Random(42)
        ts = generate_true_state(G, ["C"])
        return [simulate_response(CUR.items["i.D.1"], ["D"], G.concepts, ts, rng) for _ in range(50)]

    assert run() == run()


def test_blame_parent_baseline() -> None:
    mastery = {"A": 0.9, "B": 0.8, "C": 0.7, "D": 0.3, "E": 0.4, "F": 0.2}
    assert baseline_blame_parent(G, mastery, "F") == "E"  # weaker of F's parents C (0.7) and E (0.4)
    assert baseline_blame_parent(G, mastery, "A") == "A"  # no parents: blames itself
    assert baseline_blame_parent(G, {**mastery, "C": 0.4}, "F") == "C"  # tie broken by id
    with pytest.raises(UnknownConceptError):
        baseline_blame_parent(G, mastery, "Z")


def test_flat_bkt_only_moves_the_primary_concept() -> None:
    m = {"A": 0.3, "B": 0.3}
    out = flat_bkt_update(m, "A", concept("A"), 0.1, 0.2, True)
    assert out["B"] == 0.3 and out["A"] > 0.3
    assert baseline_flat_bkt_predict("A", {"A": 0.5}, 0.1, 0.2) == pytest.approx(0.55)


def test_metrics() -> None:
    assert top_k_accuracy([["a", "b"], ["c", "a"], ["z", "y"]], ["a", "a", "a"], 1) == pytest.approx(1 / 3)
    assert top_k_accuracy([["a", "b"], ["c", "a"], ["z", "y"]], ["a", "a", "a"], 2) == pytest.approx(2 / 3)
    with pytest.raises(InvalidParameterError):
        top_k_accuracy([["a"]], ["a", "b"], 1)

    assert brier_score([1.0, 0.0], [True, False]) == 0.0
    assert brier_score([0.5, 0.5], [True, False]) == 0.25
    assert auc([0.9, 0.8, 0.2, 0.1], [True, True, False, False]) == 1.0
    assert auc([0.1, 0.2, 0.8, 0.9], [True, True, False, False]) == 0.0
    assert auc([0.5, 0.5], [True, False]) == 0.5  # tie
    assert auc([0.3, 0.7], [True, True]) == 0.5  # one class only


def test_reliability_bins() -> None:
    bins = reliability_bins([0.05, 0.05, 0.95, 0.95, 1.0], [False, False, True, False, True], n_bins=10)
    assert [b.count for b in bins] == [2, 3]
    assert bins[0].p_obs_mean == 0.0 and bins[0].p_pred_mean == pytest.approx(0.05)
    assert bins[1].p_obs_mean == pytest.approx(2 / 3) and bins[1].p_pred_mean == pytest.approx(
        0.9667, abs=1e-3
    )
    assert sum(b.count for b in bins) == 5  # p == 1.0 lands in the last bin, nothing lost
