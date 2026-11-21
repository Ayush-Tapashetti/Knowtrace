"""Evaluate the diagnosis on simulated students: `python -m knowtrace.cli.run_eval`.

Prints accuracy against two baselines and a calibration table, saves the run so the Evaluation page
shows it, and exits non-zero when the thresholds are not met (so it can gate CI).
Offline and deterministic: no model, no network.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlmodel import Session

from knowtrace.core.db import get_engine, init_db
from knowtrace.core.settings import get_settings
from knowtrace.services import eval_runner as ev
from knowtrace.services.curriculum import seed_from_dir

LABEL = {
    ev.GRAPH: "KnowTrace (graph + Bayes)",
    ev.PARENT: "Blame direct parent",
    ev.FLAT: "Flat BKT, no graph",
}
COLS = [
    ("top1", "top-1", True),
    ("top3", "top-3", True),
    ("top1_depth2plus", "top-1 deep", True),
    ("probes_mean", "probes", False),
    ("auc", "AUC", False),
    ("brier", "Brier", False),
]


def _cell(report: ev.EvalReport, method: str, key: str, pct: bool) -> str:
    try:
        v = report.value(method, key)
    except KeyError:
        return "-"
    if key in {"auc", "brier"} and method == ev.PARENT:
        return "-"
    return f"{v * 100:.1f}%" if pct else f"{v:.2f}"


def render(report: ev.EvalReport) -> str:
    lines = [f"{'method':<28}" + "".join(f"{c[1]:>12}" for c in COLS)]
    for m in (ev.GRAPH, ev.PARENT, ev.FLAT):
        lines.append(f"{LABEL[m]:<28}" + "".join(f"{_cell(report, m, k, p):>12}" for k, _l, p in COLS))
    bins = next(d for m, k, _v, _n, d in report.metrics if m == ev.GRAPH and k == "reliability")
    lines += [
        "",
        "Calibration of next-answer predictions (KnowTrace)",
        f"{'predicted':>10}{'observed':>10}{'count':>8}",
    ]
    lines += [
        f"{b['p_pred_mean']:>10.2f}{b['p_obs_mean']:>10.2f}{b['count']:>8}"
        for b in (bins or {}).get("bins", [])
    ]
    lines.append(f"expected calibration error: {report.value(ev.GRAPH, 'reliability'):.3f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--students", type=int, default=ev.EvalParams.students)
    ap.add_argument("--seed", type=int, default=ev.EvalParams.seed)
    ap.add_argument(
        "--warmup",
        type=int,
        default=ev.EvalParams.warmup,
        help="answers each simulated student gives before the failure",
    )
    ap.add_argument("--dir", type=Path, default=Path(get_settings().curriculum_dir))
    ap.add_argument(
        "--min-top1",
        type=float,
        default=0.55,
        help="gate: top-1 accuracy (regression guard, ~10 points under measured)",
    )
    ap.add_argument("--max-ece", type=float, default=0.12, help="gate: calibration error")
    ap.add_argument("--no-save", action="store_true", help="print only; do not store the run")
    args = ap.parse_args(argv)

    init_db()
    with Session(get_engine()) as session:
        _, bundle = seed_from_dir(session, args.dir, auto_reseed=get_settings().auto_reseed)
        report = ev.run_experiment(
            bundle, ev.EvalParams(students=args.students, seed=args.seed, warmup=args.warmup)
        )
        run_id = None if args.no_save else ev.persist(session, report)

    print(
        f"{len(report.cases)} simulated students (skipped {report.skipped}), "
        f"seed {args.seed}, curriculum {report.curriculum_hash[:12]}"
    )
    print(render(report))
    for c in ev.misses(report):
        print(
            f"MISS case {c.case}: true root {c.root} (depth {c.depth}), item {c.failed_item}, "
            f"verdict {c.verdict}, top guess {c.graph_rank[0]}"
        )
    print(
        "model path: not used (deterministic core), fallback rate n/a; "
        f"{report.seconds_per_student * 1000:.1f} ms per student"
    )
    if run_id:
        print(f"saved run {run_id}")

    top1, ece = report.value(ev.GRAPH, "top1"), report.value(ev.GRAPH, "reliability")
    best_base = max(report.value(ev.PARENT, "top1"), report.value(ev.FLAT, "top1"))
    failures = []
    if top1 < args.min_top1:
        failures.append(f"top-1 {top1:.1%} below {args.min_top1:.0%}")
    if top1 <= best_base:
        failures.append(f"does not beat the best baseline ({best_base:.1%})")
    if ece > args.max_ece:
        failures.append(f"calibration error {ece:.3f} above {args.max_ece}")
    print("RESULT:", "FAIL - " + "; ".join(failures) if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
