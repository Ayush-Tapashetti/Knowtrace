"""D1/D2: the evaluation harness is deterministic, bounded, beats its baselines, and feeds the API."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from knowtrace.core.db import init_db, make_engine
from knowtrace.main import create_app
from knowtrace.services import eval_runner as ev
from knowtrace.services.bundle import CurriculumBundle
from knowtrace.services.curriculum import seed_from_dir
from tests.api.support import make_settings

SEED = Path(__file__).resolve().parents[1] / "content" / "seed"
SMALL = ev.EvalParams(students=80, seed=3)


@pytest.fixture(scope="module")
def bundle() -> Iterator[CurriculumBundle]:
    eng = make_engine("sqlite://")
    init_db(eng)
    with Session(eng) as s:
        _, b = seed_from_dir(s, SEED, auto_reseed=False)
    yield b
    eng.dispose()


@pytest.fixture(scope="module")
def report(bundle: CurriculumBundle) -> ev.EvalReport:
    return ev.run_experiment(bundle, SMALL)


def test_same_seed_same_numbers(bundle: CurriculumBundle, report: ev.EvalReport) -> None:
    assert ev.run_experiment(bundle, SMALL).metrics == report.metrics


def test_different_seed_changes_cases(bundle: CurriculumBundle, report: ev.EvalReport) -> None:
    other = ev.run_experiment(bundle, ev.EvalParams(students=80, seed=4))
    assert [c.root for c in other.cases] != [c.root for c in report.cases]


def test_metrics_are_in_range(report: ev.EvalReport) -> None:
    for _m, key, value, n, _d in report.metrics:
        assert n > 0
        if key in {"top1", "top3", "top1_depth2plus", "auc", "brier", "reliability"}:
            assert 0.0 <= value <= 1.0, key
    assert 0.0 < report.value(ev.GRAPH, "probes_mean") <= 4.0  # P0-3: at most 4 probes


def test_graph_method_beats_both_baselines_on_root_cause(report: ev.EvalReport) -> None:
    g = report.value(ev.GRAPH, "top1")
    assert g > report.value(ev.PARENT, "top1") + 0.15
    assert g > report.value(ev.FLAT, "top1") + 0.15
    assert report.value(ev.GRAPH, "top3") >= g
    assert report.value(ev.GRAPH, "top1_depth2plus") > 0.45  # gaps at depth >= 2, not just direct parents


def test_reliability_bins_are_complete_and_calibration_is_reasonable(report: ev.EvalReport) -> None:
    detail = next(d for m, k, _v, _n, d in report.metrics if m == ev.GRAPH and k == "reliability")
    assert detail is not None
    bins = detail["bins"]
    assert bins and all(set(b) == {"p_pred_mean", "p_obs_mean", "count"} for b in bins)
    assert sum(b["count"] for b in bins) == next(
        n for m, k, _v, n, _d in report.metrics if m == ev.GRAPH and k == "auc"
    )
    assert report.value(ev.GRAPH, "reliability") < 0.15


def test_saved_run_is_served_by_the_api_and_matches_the_ui_contract(
    bundle: CurriculumBundle, report: ev.EvalReport
) -> None:
    eng = make_engine("sqlite://")
    init_db(eng)
    with Session(eng) as s:
        seed_from_dir(s, SEED, auto_reseed=False)
        run_id = ev.persist(s, report)
    app = create_app(make_settings(SEED), engine=eng)
    with TestClient(app) as c:
        r = c.get("/api/v1/eval/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == run_id and body["n_students"] == len(report.cases)
    methods = {m["method"] for m in body["metrics"]}
    assert methods == {ev.GRAPH, ev.PARENT, ev.FLAT}
    rel = next(m for m in body["metrics"] if m["metric"] == "reliability")
    assert {"p_pred_mean", "p_obs_mean", "count"} <= set(rel["detail"]["bins"][0])
    eng.dispose()


@pytest.fixture
def cli_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    from knowtrace.core.db import get_engine
    from knowtrace.core.settings import get_settings

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cli.db'}")
    get_settings.cache_clear()
    get_engine.cache_clear()
    yield
    get_engine().dispose()
    get_settings.cache_clear()
    get_engine.cache_clear()


def test_cli_exit_code_gates_on_thresholds(cli_env: None, capsys: pytest.CaptureFixture[str]) -> None:
    from knowtrace.cli.run_eval import main

    common = ["--students", "60", "--dir", str(SEED), "--no-save"]
    assert main([*common, "--min-top1", "0.3"]) == 0
    out = capsys.readouterr().out
    assert (
        "RESULT: PASS" in out and "KnowTrace (graph + Bayes)" in out and "expected calibration error" in out
    )
    assert main([*common, "--min-top1", "0.99"]) == 1
    assert "RESULT: FAIL" in capsys.readouterr().out
