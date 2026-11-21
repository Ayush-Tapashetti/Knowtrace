"""Helpers for API tests: write the domain fixture curriculum as seed JSON, and drive the flows."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from knowtrace.core.db import make_engine
from knowtrace.core.settings import Settings
from knowtrace.integrations.llm_client import LLMClient
from knowtrace.main import create_app
from tests.domain.fixture import EDGES, build
from tests.integrations.helpers import NAMES, ORIGINAL

API = "/api/v1"
START = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw: float) -> None:
        self.now += timedelta(**kw)


def write_seed(directory: Path) -> Path:
    cur = build()
    directory.mkdir(parents=True, exist_ok=True)
    files: dict[str, Any] = {
        "concepts": [
            {
                "id": c.id,
                "name": NAMES[c.id],
                "description": f"About {NAMES[c.id]}",
                "strand": "fractions",
                "tier": c.tier,
                "p_init": c.p_init,
                "p_learn": c.p_learn,
                "p_slip": c.p_slip,
                "p_guess": c.p_guess,
                "p_forget": c.p_forget,
                "half_life_days": c.half_life_days,
            }
            for c in cur.graph.concepts.values()
        ],
        "edges": [{"concept_id": c, "prereq_id": p} for c, p in EDGES],
        "items": [
            {
                "id": i.id,
                "stem": f"Question {i.id}",
                "kind": "MCQ",
                "answer": i.answer,
                "choices": [{"id": x, "text": f"option {x}"} for x in i.choices],
                "difficulty": i.difficulty,
                "p_guess": i.p_guess,
            }
            for i in cur.items.values()
        ],
        "item_concepts": [
            {"item_id": iid, "concept_id": c, "is_primary": c == row.primary}
            for iid, row in cur.qmatrix.items()
            for c in row.concepts
        ],
        "atoms": [
            {
                "id": a.id,
                "concept_id": a.concept_id,
                "kind": a.kind.value,
                "est_seconds": a.est_seconds,
                "order_hint": a.order_hint,
                "item_id": a.item_id,
                "body": "" if a.item_id else ORIGINAL,
            }
            for a in cur.atoms
        ],
    }
    for name, rows in files.items():
        (directory / f"{name}.json").write_text(json.dumps(rows), encoding="utf-8")
    return directory


def make_settings(seed_dir: Path | None, **overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "sqlite://",
        "curriculum_dir": str(seed_dir) if seed_dir else "./nowhere",
        "rate_limit_per_minute": 100_000,
        "cors_origins": ["http://localhost:5173"],
    }
    return Settings(_env_file=None, **{**base, **overrides})


def make_client(
    seed_dir: Path | None,
    *,
    clock: Clock | None = None,
    llm: LLMClient | None = None,
    raise_server_exceptions: bool = True,
    **overrides: Any,
) -> TestClient:
    app = create_app(
        make_settings(seed_dir, **overrides),
        engine=make_engine("sqlite://"),
        llm_client=llm,
        clock=clock or Clock(),
    )
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def new_student(c: TestClient) -> str:
    r = c.post(f"{API}/students", json={})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def attempt(c: TestClient, sid: str, item: str, answer: str) -> dict[str, Any]:
    r = c.post(f"{API}/students/{sid}/attempts", json={"item_id": item, "answer": answer})
    assert r.status_code == 201, r.text
    return dict(r.json())


def teach(c: TestClient, sid: str, concepts: str = "ABCDEF", rounds: int = 3) -> None:
    """Correct practice answers so the learner starts out strong (raises priors)."""
    for _ in range(rounds):
        for k in concepts:
            for n in (1, 2, 3):
                attempt(c, sid, f"i.{k}.{n}", "a")


Truth = Callable[[list[str]], bool]


def knows_unless_missing(missing: set[str], desc: dict[str, set[str]]) -> Truth:
    """A learner who lacks `missing` and everything downstream of it."""
    broken = set(missing)
    for m in missing:
        broken |= desc[m]
    return lambda concepts: not (set(concepts) & broken)


DESC = {"A": set("BCDEF"), "B": set("CDEF"), "C": set("DF"), "D": set(), "E": set("F"), "F": set()}


def probe_until_done(c: TestClient, diagnosis: dict[str, Any], truth: Truth) -> dict[str, Any]:
    d = diagnosis
    for _ in range(10):
        if d["state"] != "PROBING":
            return d
        item = d["pending_item"]
        assert item is not None and d["pending_kind"] == "PROBE"
        ans = "a" if truth(item["concept_ids"]) else "b"
        r = c.post(f"{API}/diagnoses/{d['id']}/answer", json={"answer": ans})
        assert r.status_code == 200, r.text
        d = r.json()["diagnosis"]
    raise AssertionError("diagnosis did not finish")
