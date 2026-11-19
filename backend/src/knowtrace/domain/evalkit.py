"""Evaluation harness pieces (D1, D2): synthetic students, baselines, and metrics."""

from __future__ import annotations

import random
from collections.abc import Collection, Mapping, Sequence

from knowtrace.domain.bkt import bkt_posterior, bkt_transition, clamp_prob, effective_item_params
from knowtrace.domain.errors import InvalidParameterError, UnknownConceptError
from knowtrace.domain.types import ConceptSpec, Graph, ItemSpec, Prob, ReliabilityBin


def generate_true_state(graph: Graph, root_gaps: Collection[str]) -> dict[str, bool]:
    """Ground truth for a synthetic student: mastered iff not a gap and not downstream of one."""
    broken: set[str] = set()
    for g in root_gaps:
        if g not in graph.concepts:
            raise UnknownConceptError(g)
        broken.add(g)
        broken |= graph.desc[g]
    return {cid: cid not in broken for cid in graph.order}


def simulate_response(
    item: ItemSpec,
    concept_ids: Sequence[str],
    specs: Mapping[str, ConceptSpec],
    true_state: Mapping[str, bool],
    rng: random.Random,
    *,
    slip: Prob | None = None,
    guess: Prob | None = None,
) -> bool:
    """Correct with `1 - slip` if every required concept is truly mastered, else with `guess`.

    `slip`/`guess` override the model's own parameters, so the eval can test a *mismatched*
    student. This is the only function in the domain that uses randomness, via the injected `rng`.
    """
    s, g = effective_item_params(item, [specs[c] for c in concept_ids])
    s = s if slip is None else slip
    g = g if guess is None else guess
    p_correct = 1.0 - s if all(true_state[c] for c in concept_ids) else g
    return rng.random() < p_correct


def baseline_blame_parent(graph: Graph, mastery: Mapping[str, Prob], primary_concept: str) -> str:
    """Baseline: blame the weakest *direct* prerequisite of the failed item's primary concept
    (the concept itself if it has none). Ties go to the lowest id."""
    if primary_concept not in graph.concepts:
        raise UnknownConceptError(primary_concept)
    pars = graph.parents[primary_concept]
    if not pars:
        return primary_concept
    return min(pars, key=lambda c: (mastery[c], c))


def flat_bkt_update(
    mastery: Mapping[str, Prob],
    primary_concept: str,
    spec: ConceptSpec,
    slip: Prob,
    guess: Prob,
    correct: bool,
) -> dict[str, Prob]:
    """Classic single-skill BKT: only the primary concept moves, no Q-matrix, no graph."""
    out = dict(mastery)
    out[primary_concept] = bkt_transition(
        bkt_posterior(mastery[primary_concept], correct, slip, guess), spec.p_learn, spec.p_forget
    )
    return out


def baseline_flat_bkt_predict(
    primary_concept: str, mastery_flat: Mapping[str, Prob], slip: Prob, guess: Prob
) -> Prob:
    """Flat-BKT prediction: P(correct) from the primary concept's mastery alone."""
    p = clamp_prob(mastery_flat[primary_concept])
    return clamp_prob(p * (1.0 - slip) + (1.0 - p) * guess)


def top_k_accuracy(predictions: Sequence[Sequence[str]], truths: Sequence[str], k: int) -> float:
    """Fraction of cases whose true concept is within the first `k` predictions."""
    if len(predictions) != len(truths):
        raise InvalidParameterError("predictions and truths differ in length")
    if k < 1 or not truths:
        raise InvalidParameterError("need k >= 1 and at least one case")
    return sum(t in list(p)[:k] for p, t in zip(predictions, truths, strict=True)) / len(truths)


def brier_score(pred: Sequence[Prob], obs: Sequence[bool]) -> float:
    if len(pred) != len(obs) or not obs:
        raise InvalidParameterError("need equal, non-empty pred and obs")
    return sum((p - (1.0 if o else 0.0)) ** 2 for p, o in zip(pred, obs, strict=True)) / len(obs)


def auc(pred: Sequence[Prob], obs: Sequence[bool]) -> float:
    """Area under the ROC curve (Mann-Whitney, ties count half). 0.5 if only one class is present."""
    if len(pred) != len(obs):
        raise InvalidParameterError("pred and obs differ in length")
    pos = [p for p, o in zip(pred, obs, strict=True) if o]
    neg = [p for p, o in zip(pred, obs, strict=True) if not o]
    if not pos or not neg:
        return 0.5
    wins = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def reliability_bins(pred: Sequence[Prob], obs: Sequence[bool], n_bins: int = 10) -> list[ReliabilityBin]:
    """Calibration table: per non-empty bin, mean predicted vs observed frequency."""
    if len(pred) != len(obs) or n_bins < 1:
        raise InvalidParameterError("need equal-length inputs and n_bins >= 1")
    sums = [[0.0, 0.0, 0] for _ in range(n_bins)]
    for p, o in zip(pred, obs, strict=True):
        i = min(int(p * n_bins), n_bins - 1)
        sums[i][0] += p
        sums[i][1] += 1.0 if o else 0.0
        sums[i][2] += 1
    return [ReliabilityBin(s[0] / s[2], s[1] / s[2], int(s[2])) for s in sums if s[2] > 0]
