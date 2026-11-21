"""Cross-cutting behaviour: error envelope, CORS, rate limit, optional model, contract, layering."""

from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from knowtrace.cli.export_openapi import DEFAULT_OUT, render
from knowtrace.core.ratelimit import RateLimitMiddleware
from knowtrace.integrations.llm_client import FakeLLMClient
from tests.api.support import (
    API,
    DESC,
    attempt,
    knows_unless_missing,
    make_client,
    new_student,
    probe_until_done,
)
from tests.integrations.helpers import GOOD, reply

BACKEND_SRC = Path(__file__).resolve().parents[2] / "src" / "knowtrace"


# --- error envelope ----------------------------------------------------------------------------
def test_unknown_route_and_wrong_method_use_the_envelope(client: TestClient) -> None:
    r = client.get(f"{API}/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = client.delete(f"{API}/concepts")
    assert r.status_code == 405 and r.json()["error"]["code"] == "method_not_allowed"


def test_unexpected_errors_do_not_leak_internals(seed_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from knowtrace.services import curriculum

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("secret internal detail /etc/passwd")

    monkeypatch.setattr(curriculum, "graph_view", boom)
    with make_client(seed_dir, raise_server_exceptions=False) as c:
        r = c.get(f"{API}/graph")
    assert r.status_code == 500
    assert r.json() == {
        "error": {"code": "internal_error", "message": "Something went wrong on our side.", "details": None}
    }
    assert "secret" not in r.text and "Traceback" not in r.text


def test_lesson_falls_back_to_item_bank_steps_when_no_atoms_exist(seed_dir: Path) -> None:
    """With no authored atoms the assembler uses bare item-bank questions (LessonStep.atom_id is null)."""
    from sqlmodel import Session, delete

    from knowtrace.models import LessonAtom

    with make_client(seed_dir) as c:
        with Session(c.app.state.engine) as s:  # type: ignore[attr-defined]
            s.exec(delete(LessonAtom))  # type: ignore[call-overload]
            s.commit()
        c.app.state.bundle = None  # type: ignore[attr-defined]  (force a reload that sees no atoms)
        sid = new_student(c)
        for _ in range(2):
            for n in (1, 2, 3):
                attempt(c, sid, f"i.A.{n}", "a")
        d = probe_until_done(c, attempt(c, sid, "i.D.1", "b")["diagnosis"], knows_unless_missing({"B"}, DESC))
        assert d["verdict"] == "GAP" and d["state"] == "LESSON_ASSIGNED"
        lesson = c.get(f"{API}/lessons/{d['lesson_id']}").json()
    assert lesson["steps"] and all(s["item"] and s["text"] is None for s in lesson["steps"])


# --- CORS ---------------------------------------------------------------------------------------
def test_cors_allows_only_the_configured_origin(client: TestClient) -> None:
    ok = client.get(f"{API}/health", headers={"Origin": "http://localhost:5173"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-credentials" not in ok.headers
    other = client.get(f"{API}/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers
    pre = client.options(
        f"{API}/students",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert pre.status_code == 200 and "POST" in pre.headers["access-control-allow-methods"]
    assert "DELETE" not in pre.headers["access-control-allow-methods"]


# --- rate limit -----------------------------------------------------------------------------------
def test_rate_limit_returns_429_envelope_with_retry_after(seed_dir: Path) -> None:
    with make_client(seed_dir, rate_limit_per_minute=3) as c:
        codes = [c.get(f"{API}/status").status_code for _ in range(5)]
        limited = c.get(f"{API}/status")
        assert c.get("/health").status_code == 200  # liveness is exempt
    assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429]
    assert limited.json()["error"]["code"] == "rate_limited" and int(limited.headers["retry-after"]) >= 1


def test_token_bucket_refills_over_time() -> None:
    now = [0.0]
    sent: list[dict] = []

    async def app(scope, receive, send):  # type: ignore[no-untyped-def]
        await send({"type": "http.response.start", "status": 200, "headers": []})

    mw = RateLimitMiddleware(app, per_minute=60, clock=lambda: now[0])

    async def call() -> int:
        sent.clear()

        async def send(msg: dict) -> None:
            sent.append(msg)

        await mw({"type": "http", "method": "GET", "path": "/x", "client": ("1.2.3.4", 1)}, None, send)  # type: ignore[arg-type]
        return int(sent[0]["status"])

    assert [asyncio.run(call()) for _ in range(61)].count(429) == 1  # 60 allowed at t=0
    now[0] += 1.0  # one token per second
    assert asyncio.run(call()) == 200 and asyncio.run(call()) == 429


# --- optional model (D3) ----------------------------------------------------------------------------
def _lesson_sources(c: TestClient) -> list[str]:
    sid = new_student(c)
    for _ in range(2):
        for n in (1, 2, 3):
            attempt(c, sid, f"i.A.{n}", "a")
    d = probe_until_done(c, attempt(c, sid, "i.D.1", "b")["diagnosis"], knows_unless_missing({"B"}, DESC))
    lesson = c.get(f"{API}/lessons/{d['lesson_id']}").json()
    return [s["source"] for s in lesson["steps"] if s["text"]]


def test_model_text_is_labelled_and_cached(seed_dir: Path) -> None:
    llm = FakeLLMClient([reply(GOOD)])
    with make_client(
        seed_dir,
        llm=llm,
        deterministic_only=False,
        llm_rephrase_enabled=True,
        anthropic_api_key="placeholder-not-a-real-key",
    ) as c:
        assert c.get(f"{API}/status").json()["llm_mode"] == "model"
        sources = _lesson_sources(c)
    assert sources[0] == "model" and set(sources[1:]) <= {"cache", "model"} and "authored" not in sources
    assert len(llm.calls) == 1  # identical masked input is served from the cache afterwards


def test_a_bad_model_reply_falls_back_to_authored_text(seed_dir: Path) -> None:
    llm = FakeLLMClient([reply("Add.")])  # guard rejects: length ratio
    with make_client(
        seed_dir,
        llm=llm,
        deterministic_only=False,
        llm_rephrase_enabled=True,
        anthropic_api_key="placeholder-not-a-real-key",
    ) as c:
        sources = _lesson_sources(c)
    assert set(sources) == {"fallback"}


def test_default_is_deterministic_and_never_calls_a_model(client: TestClient) -> None:
    assert set(_lesson_sources(client)) == {"authored"}


# --- contract -------------------------------------------------------------------------------------
def test_exported_openapi_is_current() -> None:
    assert DEFAULT_OUT.is_file(), "run: python -m knowtrace.cli.export_openapi"
    assert DEFAULT_OUT.read_text(encoding="utf-8") == render(), "docs/openapi.json is stale; re-export it"


def test_every_endpoint_declares_the_error_envelope_and_a_typed_response() -> None:
    spec = json.loads(render())
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            assert op["operationId"] and op["summary"], (method, path)
            ok = next(r for code, r in op["responses"].items() if code.startswith("2"))
            assert (
                "$ref" in ok["content"]["application/json"]["schema"]
                or ok["content"]["application/json"]["schema"].get("type") == "array"
            ), (method, path)
            assert op["responses"]["422"]["content"]["application/json"]["schema"]["$ref"].endswith(
                "ErrorEnvelope"
            )
    assert "answer" not in spec["components"]["schemas"]["ItemOut"]["properties"]
    for name, schema in spec["components"]["schemas"].items():
        if name.endswith(("Create", "Request")):
            assert schema.get("additionalProperties") is False, name


# --- layering ---------------------------------------------------------------------------------------
def _imports(path: Path) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def test_no_router_imports_persistence_or_integrations() -> None:
    banned = (
        "knowtrace.models",
        "knowtrace.repositories",
        "knowtrace.integrations",
        "sqlmodel",
        "sqlalchemy",
    )
    for f in sorted((BACKEND_SRC / "routers").glob("*.py")):
        bad = [m for m in _imports(f) if m.startswith(banned)]
        assert not bad, f"{f.name} imports {bad}"


def test_routers_stay_thin() -> None:
    """Handlers are one service call; any branching beyond HTTP parsing belongs in a service."""
    for f in sorted((BACKEND_SRC / "routers").glob("*.py")):
        if f.name in {"errors.py", "__init__.py"}:
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
            branches = [n for n in ast.walk(fn) if isinstance(n, ast.If | ast.For | ast.While | ast.Try)]
            assert not branches, f"{f.name}:{fn.name} has logic; move it into a service"
