"""Bayesian Knowledge Tracing with multi-concept (noisy-AND) items and time-based forgetting."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from knowtrace.domain.enums import ItemKind
from knowtrace.domain.errors import (
    InvalidParameterError,
    InvalidProbabilityError,
    QMatrixError,
    UnknownConceptError,
)
from knowtrace.domain.types import ConceptSpec, ItemSpec, Observation, Prob, QRow

EPS = 1e-6


def clamp_prob(x: float, eps: float = EPS) -> Prob:
    """Clamp into [eps, 1 - eps]. NaN is an error, never silently clamped."""
    if math.isnan(x):
        raise InvalidProbabilityError("probability is NaN")
    return min(max(x, eps), 1.0 - eps)


def effective_item_params(item: ItemSpec, concept_specs: Sequence[ConceptSpec]) -> tuple[Prob, Prob]:
    """`(slip, guess)` for an item: its own override, else concept means (MCQ guess = 1/choices)."""
    if not concept_specs:
        raise QMatrixError(f"item {item.id!r} has no concepts")
    mean_slip = sum(c.p_slip for c in concept_specs) / len(concept_specs)
    slip = item.p_slip if item.p_slip is not None else mean_slip
    if item.p_guess is not None:
        guess = item.p_guess
    elif item.kind is ItemKind.MCQ and item.choices:
        guess = 1.0 / len(item.choices)
    else:
        guess = sum(c.p_guess for c in concept_specs) / len(concept_specs)
    return clamp_prob(slip), clamp_prob(guess)


def bkt_posterior(p: Prob, correct: bool, slip: Prob, guess: Prob) -> Prob:
    """Evidence step for one concept: P(mastered | answer)."""
    p, slip, guess = clamp_prob(p), clamp_prob(slip), clamp_prob(guess)
    if correct:
        num, other = p * (1.0 - slip), (1.0 - p) * guess
    else:
        num, other = p * slip, (1.0 - p) * (1.0 - guess)
    return clamp_prob(num / (num + other))


def bkt_transition(p: Prob, learn: Prob, forget: Prob) -> Prob:
    """Learning/forgetting step between opportunities: p(1-forget) + (1-p)·learn."""
    return clamp_prob(p * (1.0 - forget) + (1.0 - p) * learn)


def apply_time_forgetting(p: Prob, elapsed_days: float, half_life_days: float, floor: Prob) -> Prob:
    """Decay mastery toward `floor`: floor + (p - floor)·0.5^(elapsed/half_life). Negative time = 0."""
    if half_life_days <= 0 or math.isnan(elapsed_days):
        raise InvalidParameterError("half_life_days must be > 0 and elapsed_days a number")
    t = max(0.0, elapsed_days)
    return clamp_prob(floor + (p - floor) * 0.5 ** (t / half_life_days))


def _m(mastery: Mapping[str, Prob], concept_id: str) -> Prob:
    try:
        return clamp_prob(mastery[concept_id])
    except KeyError:
        raise UnknownConceptError(concept_id) from None


def item_success_probability(
    concept_ids: Sequence[str], mastery: Mapping[str, Prob], slip: Prob, guess: Prob
) -> Prob:
    """Noisy-AND: P(correct) = Π p_c·(1-slip) + (1 - Π p_c)·guess."""
    prod = 1.0
    for cid in concept_ids:
        prod *= _m(mastery, cid)
    return clamp_prob(prod * (1.0 - slip) + (1.0 - prod) * guess)


def multi_concept_evidence(
    mastery: Mapping[str, Prob], concept_ids: Sequence[str], slip: Prob, guess: Prob, correct: bool
) -> dict[str, Prob]:
    """Exact marginal posterior of each required concept given the answer (independent priors).

    With q = Π of the *other* concepts' mastery:
      correct: P(c|ok)  = p·A / (p·A + (1-p)·g),  A = q(1-s) + (1-q)g
      wrong:   P(c|bad) = p·B / (p·B + (1-p)(1-g)), B = q·s + (1-q)(1-g)
    Single-concept items (q = 1) reduce to `bkt_posterior`.
    """
    probs = {cid: _m(mastery, cid) for cid in concept_ids}
    out: dict[str, Prob] = {}
    for cid, p in probs.items():
        q = 1.0
        for other, po in probs.items():
            if other != cid:
                q *= po
        if correct:
            like_mastered = q * (1.0 - slip) + (1.0 - q) * guess
            like_not = guess
        else:
            like_mastered = q * slip + (1.0 - q) * (1.0 - guess)
            like_not = 1.0 - guess
        num = p * like_mastered
        out[cid] = clamp_prob(num / (num + (1.0 - p) * like_not))
    return out


def update_mastery_from_attempt(
    mastery: Mapping[str, Prob],
    item: ItemSpec,
    concept_ids: Sequence[str],
    specs: Mapping[str, ConceptSpec],
    correct: bool,
) -> dict[str, Prob]:
    """Evidence step for every required concept (from the pre-update marginals), then each
    concept's own learn/forget transition. Concepts not in the item are returned unchanged.

    Note: the *evidence* step never moves a concept against the answer. The transition after it
    may nudge a very high mastery down slightly (forgetting), so compare outcomes for the same
    prior (correct >= wrong) rather than assuming a correct answer always raises the final value.
    """
    try:
        concept_specs = [specs[cid] for cid in concept_ids]
    except KeyError as exc:
        raise UnknownConceptError(str(exc.args[0])) from None
    slip, guess = effective_item_params(item, concept_specs)
    evidence = multi_concept_evidence(mastery, concept_ids, slip, guess, correct)
    out = dict(mastery)
    for cid in concept_ids:
        spec = specs[cid]
        out[cid] = bkt_transition(evidence[cid], spec.p_learn, spec.p_forget)
    return out


def replay_attempts(
    initial_mastery: Mapping[str, Prob],
    attempts: Sequence[Observation],
    items: Mapping[str, ItemSpec],
    qmatrix: Mapping[str, QRow],
    specs: Mapping[str, ConceptSpec],
) -> dict[str, Prob]:
    """Fold attempts in `seq` order. Must equal the stored MasteryState (time decay is applied
    on read, never stored, so it does not affect this invariant)."""
    mastery = dict(initial_mastery)
    for obs in sorted(attempts, key=lambda o: o.seq):
        if obs.item_id not in items or obs.item_id not in qmatrix:
            raise QMatrixError(f"unknown item {obs.item_id!r} in attempt {obs.seq}")
        mastery = update_mastery_from_attempt(
            mastery, items[obs.item_id], qmatrix[obs.item_id].concepts, specs, obs.correct
        )
    return mastery
