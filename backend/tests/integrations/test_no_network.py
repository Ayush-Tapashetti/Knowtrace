"""D3: the whole fail -> diagnose -> lesson flow runs with no key, no model and the network blocked."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from knowtrace.core.settings import Settings
from knowtrace.domain.diagnosis import run_diagnosis_episode
from knowtrace.domain.evalkit import generate_true_state
from knowtrace.domain.lesson import assemble_lesson
from knowtrace.domain.types import Gap
from knowtrace.integrations.rephraser import Rephraser
from tests.domain.fixture import CFG, build
from tests.integrations.helpers import NAMES, ORIGINAL

SRC = Path(__file__).resolve().parents[2] / "src"


def test_full_flow_with_network_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny(*_a: object, **_k: object) -> None:
        raise AssertionError("network access attempted")

    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    cur = build()
    truth = generate_true_state(cur.graph, ["B"])
    mastery = dict.fromkeys(cur.graph.order, 0.3)
    res = run_diagnosis_episode(
        cur.graph, cur.items, cur.qmatrix, mastery, "i.F.1",
        lambda item: all(truth[c] for c in cur.qmatrix[item.id].concepts), CFG,
    )  # fmt: skip
    assert isinstance(res.outcome, Gap) and res.outcome.concept == "B"

    plan = assemble_lesson(cur.graph, cur.atoms, cur.items, cur.qmatrix, mastery, "B", ["F"], CFG)
    assert plan.steps and plan.est_seconds <= CFG.lesson_budget_seconds

    rephraser = Rephraser.from_settings(Settings(_env_file=None), NAMES)  # default: deterministic only
    out = rephraser.rephrase(ORIGINAL, "B", ["B", "C"])
    assert (out.text, out.source, out.reason) == (ORIGINAL, "fallback", "disabled")


def test_importing_the_integrations_never_loads_the_model_sdk() -> None:
    code = (
        "import sys, knowtrace.integrations.rephraser, knowtrace.integrations.llm_client;"
        "bad = [m for m in ('anthropic', 'httpx2', 'httpx') if m in sys.modules];"
        "assert not bad, bad"
    )
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=False)
    assert out.returncode == 0, out.stderr
