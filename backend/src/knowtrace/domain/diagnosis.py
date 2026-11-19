"""Root-cause diagnosis over the prerequisite graph.

Model: single-root-gap hypotheses. `h_c` = "the student lacks concept c, and therefore everything
downstream of it, and has mastered the rest". `SLIP` = "everything is mastered; the failure was a
slip". Under `h_c` an item is *affected* if it requires c or any descendant of c: affected items
are answered correctly with probability `guess`, unaffected ones with `1 - slip`. Several gaps at
once are handled one after another (resolve, recheck, re-diagnose).
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Callable, Collection, Mapping, Sequence

from knowtrace.domain.bkt import clamp_prob, effective_item_params
from knowtrace.domain.config import DomainConfig
from knowtrace.domain.errors import EmptyCandidateSetError, NoPathError, QMatrixError, UnknownConceptError
from knowtrace.domain.types import (
    SLIP,
    Continue,
    DiagnosisOutcome,
    EpisodeResult,
    Gap,
    Graph,
    Inconclusive,
    ItemSpec,
    Prob,
    ProbeRecord,
    QRow,
    Ranked,
    Slip,
    Trace,
    TraceNode,
)

Posterior = dict[str, float]

_MIN_USEFUL_EIG = 1e-9


def candidate_set(graph: Graph, required_concepts: Sequence[str], excluded: Collection[str]) -> list[str]:
    """Required concepts plus all their ancestors, minus `excluded`, in topological order."""
    found: set[str] = set()
    for cid in required_concepts:
        if cid not in graph.concepts:
            raise UnknownConceptError(cid)
        found.add(cid)
        found |= graph.anc[cid]
    found -= set(excluded)
    if not found:
        raise EmptyCandidateSetError("every required concept (and prerequisite) is excluded")
    return [cid for cid in graph.order if cid in found]


def _mastery(mastery: Mapping[str, Prob], cid: str) -> Prob:
    try:
        return clamp_prob(mastery[cid])
    except KeyError:
        raise UnknownConceptError(cid) from None


def prior_over_hypotheses(graph: Graph, mastery: Mapping[str, Prob], candidates: Sequence[str]) -> Posterior:
    """π(c) ∝ (1 - p_c)·Π_{a∈parents(c)} p_a  (a *frontier* gap), π(SLIP) ∝ Π_{k∈candidates} p_k."""
    weights: dict[str, float] = {}
    for cid in candidates:
        w = 1.0 - _mastery(mastery, cid)
        for a in graph.parents[cid]:
            w *= _mastery(mastery, a)
        weights[cid] = w
    slip_w = 1.0
    for cid in candidates:
        slip_w *= _mastery(mastery, cid)
    weights[SLIP] = slip_w
    total = sum(weights.values())
    return {h: w / total for h, w in weights.items()}


def is_affected(graph: Graph, item_concepts: Sequence[str], concept_id: str) -> bool:
    """True if answering the item requires `concept_id` or something downstream of it."""
    return any(k == concept_id or concept_id in graph.anc[k] for k in item_concepts)


def observation_likelihood(
    graph: Graph,
    hypothesis: str,
    item_concepts: Sequence[str],
    slip: Prob,
    guess: Prob,
    correct: bool,
) -> Prob:
    """P(answer | hypothesis). `SLIP` never affects any item."""
    affected = hypothesis != SLIP and is_affected(graph, item_concepts, hypothesis)
    p_correct = guess if affected else 1.0 - slip
    return p_correct if correct else 1.0 - p_correct


def posterior_update(
    graph: Graph,
    post: Mapping[str, float],
    item_concepts: Sequence[str],
    slip: Prob,
    guess: Prob,
    correct: bool,
) -> Posterior:
    """Bayes update, renormalised."""
    raw = {
        h: p * observation_likelihood(graph, h, item_concepts, slip, guess, correct) for h, p in post.items()
    }
    total = sum(raw.values())
    return {h: v / total for h, v in raw.items()}


def _entropy(post: Mapping[str, float]) -> float:
    return -sum(p * math.log2(p) for p in post.values() if p > 0.0)


def expected_information_gain(
    graph: Graph,
    post: Mapping[str, float],
    item_concepts: Sequence[str],
    slip: Prob,
    guess: Prob,
) -> float:
    """Bits: H(post) - Σ_o P(o)·H(post | o). Never negative."""
    p_ok = sum(
        p * observation_likelihood(graph, h, item_concepts, slip, guess, True) for h, p in post.items()
    )
    expected_after = 0.0
    for correct, p_obs in ((True, p_ok), (False, 1.0 - p_ok)):
        if p_obs <= 0.0:
            continue
        after = {
            h: p * observation_likelihood(graph, h, item_concepts, slip, guess, correct) / p_obs
            for h, p in post.items()
        }
        expected_after += p_obs * _entropy(after)
    return max(0.0, _entropy(post) - expected_after)


def _item_params(graph: Graph, item: ItemSpec, row: QRow) -> tuple[Prob, Prob]:
    return effective_item_params(item, [graph.concepts[c] for c in row.concepts])


def _best_probe(
    graph: Graph,
    items: Mapping[str, ItemSpec],
    qmatrix: Mapping[str, QRow],
    post: Mapping[str, float],
    asked: Collection[str],
) -> tuple[ItemSpec, float] | None:
    candidates = {h for h in post if h != SLIP}
    best: tuple[ItemSpec, float] | None = None
    for item_id in sorted(items):
        if item_id in asked:
            continue
        row = qmatrix[item_id]
        if not candidates.intersection(row.concepts):
            continue
        slip, guess = _item_params(graph, items[item_id], row)
        gain = expected_information_gain(graph, post, row.concepts, slip, guess)
        if best is None or gain > best[1] + 1e-12:
            best = (items[item_id], gain)
    if best is None or best[1] < _MIN_USEFUL_EIG:
        return None
    return best


def select_next_probe(
    graph: Graph,
    items: Mapping[str, ItemSpec],
    qmatrix: Mapping[str, QRow],
    post: Mapping[str, float],
    asked_item_ids: Collection[str],
) -> ItemSpec | None:
    """Unasked item touching the candidate set with the highest expected information gain.

    `asked_item_ids` must include the item that triggered the diagnosis. Ties go to the lowest
    item id. Returns None when no item would tell the hypotheses apart.
    """
    found = _best_probe(graph, items, qmatrix, post, asked_item_ids)
    return None if found is None else found[0]


def _ranked(post: Mapping[str, float]) -> Ranked:
    return tuple(sorted(post.items(), key=lambda kv: (-kv[1], kv[0]))[:3])


def diagnosis_verdict(
    post: Mapping[str, float], probes_used: int, cfg: DomainConfig, probe_available: bool = True
) -> DiagnosisOutcome:
    """Decide whether to keep probing, call a gap or a slip, or give up.

    1. fewer than `min_probes` used -> Continue
    2. best hypothesis >= `tau_conf` -> Gap (or Slip if the best is SLIP)
    3. `max_probes` used or no useful probe left -> Inconclusive
    4. otherwise Continue
    """
    ranked = _ranked(post)
    best, p_best = ranked[0]
    if probes_used < cfg.min_probes:
        return Continue()
    if p_best >= cfg.tau_conf:
        return Slip(p_best) if best == SLIP else Gap(best, p_best, ranked)
    if probes_used >= cfg.max_probes or not probe_available:
        return Inconclusive(ranked)
    return Continue()


def explain_diagnosis(
    graph: Graph, post: Mapping[str, float], mastery: Mapping[str, Prob], target: str, root: str
) -> Trace:
    """Shortest prerequisite path `root -> target` with each node's posterior mass and mastery."""
    for cid in (root, target):
        if cid not in graph.concepts:
            raise UnknownConceptError(cid)
    prev: dict[str, str | None] = {root: None}
    queue: deque[str] = deque([root])
    while queue and target not in prev:
        node = queue.popleft()
        for ch in graph.children[node]:
            if ch not in prev:
                prev[ch] = node
                queue.append(ch)
    if target not in prev:
        raise NoPathError(f"{root!r} is not a prerequisite of {target!r}")
    path: list[str] = []
    cur: str | None = target
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return Trace(tuple(TraceNode(c, post.get(c, 0.0), _mastery(mastery, c)) for c in path))


def run_diagnosis_episode(
    graph: Graph,
    items: Mapping[str, ItemSpec],
    qmatrix: Mapping[str, QRow],
    mastery: Mapping[str, Prob],
    failed_item_id: str,
    responder: Callable[[ItemSpec], bool],
    cfg: DomainConfig,
    excluded: Collection[str] = (),
) -> EpisodeResult:
    """Open a diagnosis for a failed item, probe adaptively, and return the verdict.

    `mastery` is the state *before* the failed attempt (the failure enters through the hypothesis
    posterior, so it is never counted twice). `responder` answers each probe: the service layer
    passes the real learner's grading result, the eval harness a simulated student.
    """
    if failed_item_id not in items or failed_item_id not in qmatrix:
        raise QMatrixError(f"unknown item {failed_item_id!r}")
    row = qmatrix[failed_item_id]
    candidates = candidate_set(graph, row.concepts, excluded)
    post = prior_over_hypotheses(graph, mastery, candidates)
    slip, guess = _item_params(graph, items[failed_item_id], row)
    post = posterior_update(graph, post, row.concepts, slip, guess, False)

    asked: set[str] = {failed_item_id}
    probes: list[ProbeRecord] = []
    while True:
        found = _best_probe(graph, items, qmatrix, post, asked)
        outcome = diagnosis_verdict(post, len(probes), cfg, probe_available=found is not None)
        if not isinstance(outcome, Continue) or found is None:
            break
        probe, gain = found
        prow = qmatrix[probe.id]
        correct = responder(probe)
        pslip, pguess = _item_params(graph, probe, prow)
        post = posterior_update(graph, post, prow.concepts, pslip, pguess, correct)
        asked.add(probe.id)
        probes.append(ProbeRecord(len(probes) + 1, probe.id, correct, gain, dict(post)))

    trace: Trace | None = None
    if isinstance(outcome, Gap):
        ordered = [row.primary, *sorted(c for c in row.concepts if c != row.primary)]
        for target in ordered:
            if target == outcome.concept or outcome.concept in graph.anc[target]:
                trace = explain_diagnosis(graph, post, mastery, target, outcome.concept)
                break
    return EpisodeResult(outcome, tuple(probes), dict(post), trace)
