from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from knowtrace.domain.bkt import effective_item_params
from knowtrace.domain.config import DomainConfig
from knowtrace.domain.diagnosis import (
    candidate_set,
    diagnosis_verdict,
    expected_information_gain,
    explain_diagnosis,
    is_affected,
    observation_likelihood,
    posterior_update,
    prior_over_hypotheses,
    run_diagnosis_episode,
    select_next_probe,
)
from knowtrace.domain.errors import EmptyCandidateSetError, NoPathError, QMatrixError, UnknownConceptError
from knowtrace.domain.evalkit import generate_true_state
from knowtrace.domain.types import SLIP, Continue, Gap, Inconclusive, ItemSpec, Slip
from tests.domain.fixture import CFG, build

CUR = build()
G = CUR.graph
UNIFORM = {c: 0.3 for c in G.order}


def truthful(true_state: dict[str, bool]):
    """Noise-free student: correct iff every required concept is truly mastered."""
    return lambda item: all(true_state[c] for c in CUR.qmatrix[item.id].concepts)


def test_candidate_set_is_required_plus_ancestors_minus_excluded() -> None:
    assert candidate_set(G, ["F"], []) == ["A", "B", "C", "E", "F"]
    assert candidate_set(G, ["D"], ["A"]) == ["B", "C", "D"]
    assert candidate_set(G, ["F", "D"], []) == ["A", "B", "C", "E", "D", "F"]
    with pytest.raises(EmptyCandidateSetError):
        candidate_set(G, ["A"], ["A"])
    with pytest.raises(UnknownConceptError):
        candidate_set(G, ["Z"], [])


def test_is_affected() -> None:
    assert is_affected(G, ["F"], "B") and is_affected(G, ["F"], "F")  # F requires B transitively
    assert not is_affected(G, ["C"], "E") and not is_affected(G, ["B"], "C")  # sibling / descendant
    assert is_affected(G, ["D", "B"], "C")  # multi-concept: D needs C


def test_prior_normalised_and_favours_frontier_gaps() -> None:
    cands = candidate_set(G, ["F"], [])
    mastery = {"A": 0.95, "B": 0.95, "C": 0.2, "E": 0.9, "F": 0.1, "D": 0.5}
    pri = prior_over_hypotheses(G, mastery, cands)
    assert sum(pri.values()) == pytest.approx(1.0) and set(pri) == {*cands, SLIP}
    # C is weak with mastered parents; F is weak too but its parent C is weak, so F is not the frontier
    assert pri["C"] > pri["F"]
    assert pri[SLIP] < pri["C"]


def test_likelihood_slip_and_affected() -> None:
    args = (G, ["F"], 0.1, 0.2)
    assert observation_likelihood(G, "B", *args[1:], correct=True) == pytest.approx(0.2)
    assert observation_likelihood(G, "E", *args[1:], correct=False) == pytest.approx(0.8)
    assert observation_likelihood(G, SLIP, *args[1:], correct=True) == pytest.approx(0.9)
    assert observation_likelihood(G, "D", *args[1:], correct=True) == pytest.approx(0.9)  # D doesn't affect F


def test_posterior_update_is_bayes() -> None:
    post = {"B": 0.5, SLIP: 0.5}
    out = posterior_update(G, post, ["F"], 0.1, 0.2, False)
    # wrong answer: B -> 0.8, SLIP -> 0.1  =>  0.4 : 0.05
    assert out["B"] == pytest.approx(0.4 / 0.45) and out[SLIP] == pytest.approx(0.05 / 0.45)
    assert sum(out.values()) == pytest.approx(1.0)


@given(st.lists(st.floats(0.01, 1.0), min_size=6, max_size=6), st.floats(0.01, 0.4), st.floats(0.01, 0.4))
def test_eig_nonnegative_and_bounded_by_entropy(w: list[float], slip: float, guess: float) -> None:
    total = sum(w)
    post = {h: x / total for h, x in zip(["A", "B", "C", "E", "F", SLIP], w, strict=True)}
    for concepts in (["F"], ["A"], ["D", "B"], ["E"]):
        gain = expected_information_gain(G, post, concepts, slip, guess)
        entropy = -sum(p * math.log2(p) for p in post.values())
        assert 0.0 <= gain <= min(entropy, 1.0) + 1e-9  # one binary observation yields at most 1 bit


def test_eig_is_zero_when_the_item_cannot_discriminate() -> None:
    # every hypothesis affects an item on F identically only if all of them are ancestors-or-equal of F
    post = {"A": 0.5, "B": 0.5}
    assert expected_information_gain(G, post, ["F"], 0.1, 0.2) == pytest.approx(0.0, abs=1e-12)
    assert expected_information_gain(G, {"B": 0.5, SLIP: 0.5}, ["F"], 0.1, 0.2) > 0.1


def test_select_next_probe_is_deterministic_and_skips_asked() -> None:
    post = posterior_update(
        G, prior_over_hypotheses(G, UNIFORM, candidate_set(G, ["F"], [])), ["F"], 0.1, 0.1, False
    )
    first = select_next_probe(G, CUR.items, CUR.qmatrix, post, {"i.F.1"})
    assert first is not None
    assert first == select_next_probe(G, CUR.items, CUR.qmatrix, post, {"i.F.1"})
    again = select_next_probe(G, CUR.items, CUR.qmatrix, post, {"i.F.1", first.id})
    assert again is not None and again.id != first.id
    # items that touch no candidate are never chosen
    assert (
        select_next_probe(G, {"i.D.1": CUR.items["i.D.1"]}, CUR.qmatrix, {"A": 0.5, SLIP: 0.5}, set()) is None
    )
    everything = set(CUR.items)
    assert select_next_probe(G, CUR.items, CUR.qmatrix, post, everything) is None


def test_verdict_rules() -> None:
    cfg = DomainConfig(tau_conf=0.8, min_probes=1, max_probes=4)
    post = {"B": 0.9, SLIP: 0.1}
    assert isinstance(diagnosis_verdict(post, 0, cfg), Continue)  # min_probes not met
    v = diagnosis_verdict(post, 1, cfg)
    assert isinstance(v, Gap) and v.concept == "B" and v.confidence == pytest.approx(0.9)
    s = diagnosis_verdict({SLIP: 0.85, "B": 0.15}, 2, cfg)
    assert isinstance(s, Slip) and s.confidence == pytest.approx(0.85)
    unsure = {"A": 0.4, "B": 0.35, SLIP: 0.25}
    assert isinstance(diagnosis_verdict(unsure, 2, cfg), Continue)
    inc = diagnosis_verdict(unsure, 4, cfg)
    assert isinstance(inc, Inconclusive) and [h for h, _ in inc.ranked] == ["A", "B", SLIP]
    assert isinstance(diagnosis_verdict(unsure, 2, cfg, probe_available=False), Inconclusive)
    assert isinstance(diagnosis_verdict(post, 4, cfg), Gap)  # confident beats budget exhaustion
    assert isinstance(diagnosis_verdict({"B": 0.5, "A": 0.5}, 1, cfg), Continue)  # tie ranked by id


def test_explain_diagnosis_path() -> None:
    mastery = UNIFORM
    t = explain_diagnosis(G, {"B": 0.9}, mastery, target="F", root="B")
    assert [n.concept_id for n in t.nodes] in (["B", "C", "F"], ["B", "E", "F"])
    assert t.nodes[0].posterior_mass == 0.9 and t.nodes[-1].posterior_mass == 0.0
    assert [n.concept_id for n in explain_diagnosis(G, {}, mastery, "B", "B").nodes] == ["B"]
    with pytest.raises(NoPathError):
        explain_diagnosis(G, {}, mastery, target="B", root="F")


@pytest.mark.parametrize("gaps", [["B"], ["C"], ["E"], ["A"], ["B", "E"]])
def test_episode_finds_the_true_root_gap(gaps: list[str]) -> None:
    truth = generate_true_state(G, gaps)
    target_item = "i.F.1"
    res = run_diagnosis_episode(G, CUR.items, CUR.qmatrix, UNIFORM, target_item, truthful(truth), CFG)
    assert len(res.probes) <= CFG.max_probes
    assert sum(res.posterior.values()) == pytest.approx(1.0)
    top = max(res.posterior.items(), key=lambda kv: (kv[1], kv[0]))[0]
    # with several simultaneous gaps the diagnosis targets a frontier gap (resolved first, then re-diagnosed)
    frontier = {g for g in gaps if not (set(gaps) & G.anc[g])}
    assert top in frontier, (gaps, res.posterior)


@pytest.mark.parametrize("gap", ["B", "C", "E"])
def test_episode_reports_a_gap_with_a_trace(gap: str) -> None:
    truth = generate_true_state(G, [gap])
    res = run_diagnosis_episode(G, CUR.items, CUR.qmatrix, UNIFORM, "i.F.1", truthful(truth), CFG)
    assert isinstance(res.outcome, Gap), res
    assert res.outcome.concept == gap and res.outcome.confidence >= CFG.tau_conf
    assert res.trace is not None
    assert res.trace.nodes[0].concept_id == gap and res.trace.nodes[-1].concept_id == "F"
    assert [p.seq for p in res.probes] == list(range(1, len(res.probes) + 1))
    assert all(p.eig_bits >= 0 for p in res.probes)


def test_a_slip_is_dismissed_without_a_gap() -> None:
    truth = generate_true_state(G, [])  # everything mastered; the failure was a slip
    strong = dict.fromkeys(G.order, 0.9)  # the tracker already believes this student is strong
    res = run_diagnosis_episode(G, CUR.items, CUR.qmatrix, strong, "i.F.1", truthful(truth), CFG)
    assert isinstance(res.outcome, Slip) and res.outcome.confidence >= CFG.tau_conf
    assert res.trace is None


def test_a_weak_student_cannot_be_called_a_slip_in_four_probes() -> None:
    """With low prior mastery, 'slip' starts very unlikely, so the honest answer is not-a-slip or unsure."""
    truth = generate_true_state(G, [])
    res = run_diagnosis_episode(G, CUR.items, CUR.qmatrix, UNIFORM, "i.F.1", truthful(truth), CFG)
    assert not isinstance(res.outcome, Gap | Slip) or res.outcome.confidence >= CFG.tau_conf
    assert res.posterior[SLIP] < 0.5


def test_episode_is_deterministic_and_respects_exclusions() -> None:
    truth = generate_true_state(G, ["C"])
    run = lambda ex: run_diagnosis_episode(  # noqa: E731
        G, CUR.items, CUR.qmatrix, UNIFORM, "i.F.1", truthful(truth), CFG, excluded=ex
    )
    assert run([]) == run([])
    assert "C" not in run(["C"]).posterior  # an excluded concept is never a hypothesis again
    with pytest.raises(QMatrixError):
        run_diagnosis_episode(G, CUR.items, CUR.qmatrix, UNIFORM, "nope", truthful(truth), CFG)


def test_probe_budget_is_enforced() -> None:
    cfg = DomainConfig(tau_conf=0.999, max_probes=2)  # unreachable confidence forces the budget path
    truth = generate_true_state(G, ["B"])
    res = run_diagnosis_episode(G, CUR.items, CUR.qmatrix, UNIFORM, "i.F.1", truthful(truth), cfg)
    assert len(res.probes) <= 2 and isinstance(res.outcome, Inconclusive)


def test_effective_params_used_for_probes_match_item_overrides() -> None:
    item: ItemSpec = CUR.items["i.F.1"]
    assert effective_item_params(item, [G.concepts["F"]]) == (pytest.approx(0.1), pytest.approx(0.1))
