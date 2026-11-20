"""Synthetic-student evaluation (D1, D2): ground-truth gaps, our method against two baselines.

Protocol, per simulated student:
  1. Hide one root gap. Truth: the gap and everything downstream of it is not mastered.
  2. Warm-up: the student answers `warmup` random items; both trackers update from the answers.
     The student's slip/guess differ from the model's, so the model is deliberately mismatched.
  3. Held-out: both trackers predict `heldout` further answers (AUC, Brier, calibration).
  4. The student fails an item that depends on the gap. Each method names the root cause.

Randomness comes only from the seeded `random.Random`, so a (seed, curriculum) pair always gives the
same numbers. Everything here is deterministic and offline: no model, no network.
"""

from __future__ import annotations

import random
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session

from knowtrace.domain import evalkit
from knowtrace.domain.bkt import effective_item_params, update_mastery_from_attempt
from knowtrace.domain.config import DomainConfig
from knowtrace.domain.diagnosis import run_diagnosis_episode
from knowtrace.domain.forecast import predict_next_correct
from knowtrace.domain.types import SLIP, Gap, Slip
from knowtrace.models import EvalResult, EvalRun
from knowtrace.repositories import curriculum as repo
from knowtrace.services.bundle import CurriculumBundle

GRAPH = "graph_bayes"
PARENT = "baseline_parent"
FLAT = "baseline_flat_bkt"


@dataclass(frozen=True)
class EvalParams:
    students: int = 300
    seed: int = 7
    warmup: int = 100
    heldout: int = 20
    student_slip: float = 0.15  # the simulated student is not the model's student
    student_guess: float = 0.20


@dataclass
class CaseRow:
    case: int
    root: str
    depth: int
    failed_item: str
    verdict: str
    graph_rank: list[str]
    parent_rank: list[str]
    flat_rank: list[str]
    probes: int


@dataclass
class EvalReport:
    params: EvalParams
    curriculum_hash: str
    cases: list[CaseRow] = field(default_factory=list)
    metrics: list[tuple[str, str, float, int, dict[str, Any] | None]] = field(default_factory=list)
    skipped: int = 0
    seconds_per_student: float = 0.0

    def value(self, method: str, metric: str) -> float:
        for m, k, v, _n, _d in self.metrics:
            if m == method and k == metric:
                return v
        raise KeyError((method, metric))


def _ranking(post: Mapping[str, float]) -> list[str]:
    return [k for k, _ in sorted(post.items(), key=lambda kv: (-kv[1], kv[0]))]


def _parent_ranking(b: CurriculumBundle, mastery: Mapping[str, float], primary: str) -> list[str]:
    first = evalkit.baseline_blame_parent(b.graph, mastery, primary)
    rest = sorted((p for p in b.graph.parents[primary] if p != first), key=lambda c: (mastery[c], c))
    return list(dict.fromkeys([first, *rest, primary]))


def _one_student(
    b: CurriculumBundle, cfg: DomainConfig, p: EvalParams, rng: random.Random, case: int
) -> tuple[CaseRow, list[float], list[float], list[bool]] | None:
    g, specs = b.graph, b.graph.concepts
    roots = [c for c in g.order if g.desc[c]]
    root = rng.choice(roots)
    truth = evalkit.generate_true_state(g, [root])
    broken = {c for c, ok in truth.items() if not ok}
    ids = sorted(b.items)

    def answer(item_id: str) -> bool:
        return evalkit.simulate_response(
            b.items[item_id], b.qmatrix[item_id].concepts, specs, truth, rng,
            slip=p.student_slip, guess=p.student_guess,
        )  # fmt: skip

    graph_m = {c: specs[c].p_init for c in g.order}
    flat_m = dict(graph_m)
    warm = rng.sample(ids, p.warmup)
    for iid in warm:
        ok = answer(iid)
        row = b.qmatrix[iid]
        graph_m = update_mastery_from_attempt(graph_m, b.items[iid], row.concepts, specs, ok)
        slip, guess = effective_item_params(b.items[iid], [specs[row.primary]])
        flat_m = evalkit.flat_bkt_update(flat_m, row.primary, specs[row.primary], slip, guess, ok)

    seen = set(warm)
    held = rng.sample([i for i in ids if i not in seen], p.heldout)  # disjoint from warm-up
    pred_graph: list[float] = []
    pred_flat: list[float] = []
    obs: list[bool] = []
    for iid in held:
        row = b.qmatrix[iid]
        slip, guess = effective_item_params(b.items[iid], [specs[c] for c in row.concepts])
        pred_graph.append(predict_next_correct(row.concepts, graph_m, slip, guess))
        fs, fg = effective_item_params(b.items[iid], [specs[row.primary]])
        pred_flat.append(evalkit.baseline_flat_bkt_predict(row.primary, flat_m, fs, fg))
        obs.append(answer(iid))

    affected = [i for i in ids if broken & set(b.qmatrix[i].concepts)]
    rng.shuffle(affected)
    failed = next((i for i in affected if not answer(i)), None)
    if failed is None:
        return None
    episode = run_diagnosis_episode(g, b.items, b.qmatrix, graph_m, failed, lambda it: answer(it.id), cfg)
    primary = b.qmatrix[failed].primary
    verdict = (
        "gap"
        if isinstance(episode.outcome, Gap)
        else "slip"
        if isinstance(episode.outcome, Slip)
        else "inconclusive"
    )
    ranked = _ranking(episode.posterior)
    case_row = CaseRow(
        case,
        root,
        len(g.anc[root]),
        failed,
        verdict,
        ranked,
        _parent_ranking(b, graph_m, primary),
        [primary],
        len(episode.probes),
    )
    return case_row, pred_graph, pred_flat, obs


def run_experiment(b: CurriculumBundle, p: EvalParams, cfg: DomainConfig | None = None) -> EvalReport:
    cfg = cfg or DomainConfig()
    rng = random.Random(p.seed)
    report = EvalReport(p, b.hash)
    pg: list[float] = []
    pf: list[float] = []
    ob: list[bool] = []
    t0 = time.perf_counter()
    for case in range(p.students):
        out = _one_student(b, cfg, p, rng, case)
        if out is None:
            report.skipped += 1
            continue
        row, a, f, o = out
        report.cases.append(row)
        pg += a
        pf += f
        ob += o
    report.seconds_per_student = (time.perf_counter() - t0) / max(p.students, 1)

    n = len(report.cases)
    truths = [c.root for c in report.cases]
    rankings = {
        GRAPH: [c.graph_rank for c in report.cases],
        PARENT: [c.parent_rank for c in report.cases],
        FLAT: [c.flat_rank for c in report.cases],
    }
    add = report.metrics.append
    deep = [i for i, c in enumerate(report.cases) if c.depth >= 2]
    for method, ranks in rankings.items():
        top1 = evalkit.top_k_accuracy(ranks, truths, 1)
        by_depth: dict[str, list[bool]] = defaultdict(list)
        for c, r in zip(report.cases, ranks, strict=True):
            by_depth["2+" if c.depth >= 2 else str(c.depth)].append(r[0] == c.root)
        detail = {"by_root_depth": {k: round(sum(v) / len(v), 4) for k, v in sorted(by_depth.items())}}
        add((method, "top1", top1, n, detail))
        add((method, "top3", evalkit.top_k_accuracy(ranks, truths, 3), n, None))
        if deep:
            add(
                (
                    method,
                    "top1_depth2plus",
                    evalkit.top_k_accuracy([ranks[i] for i in deep], [truths[i] for i in deep], 1),
                    len(deep),
                    None,
                )
            )
    add((GRAPH, "probes_mean", sum(c.probes for c in report.cases) / n, n, {"max_probes": cfg.max_probes}))
    add((PARENT, "probes_mean", 0.0, n, None))
    add((FLAT, "probes_mean", 0.0, n, None))
    for method, pred in ((GRAPH, pg), (FLAT, pf)):
        add((method, "auc", evalkit.auc(pred, ob), len(ob), None))
        add((method, "brier", evalkit.brier_score(pred, ob), len(ob), None))
    bins = evalkit.reliability_bins(pg, ob)
    ece = sum(abs(x.p_pred_mean - x.p_obs_mean) * x.count for x in bins) / len(ob)
    detail_bins = {
        "bins": [{"p_pred_mean": x.p_pred_mean, "p_obs_mean": x.p_obs_mean, "count": x.count} for x in bins]
    }
    add((GRAPH, "reliability", ece, len(ob), detail_bins))
    return report


def persist(session: Session, report: EvalReport, now_version: str | None = None) -> str:
    run = EvalRun(
        seed=report.params.seed,
        n_students=len(report.cases),
        curriculum_hash=report.curriculum_hash,
        code_version=now_version,
        config={k: getattr(report.params, k) for k in report.params.__dataclass_fields__},
    )
    session.add(run)
    session.flush()
    repo.add_all(
        session,
        [
            EvalResult(run_id=run.id, method=m, metric=k, value=v, n=n, detail=d)
            for m, k, v, n, d in report.metrics
        ],
    )
    session.commit()
    return run.id


def misses(report: EvalReport, limit: int = 10) -> Sequence[CaseRow]:
    return [c for c in report.cases if c.graph_rank[0] != c.root][:limit]


__all__ = [
    "FLAT",
    "GRAPH",
    "PARENT",
    "SLIP",
    "EvalParams",
    "EvalReport",
    "misses",
    "persist",
    "run_experiment",
]
