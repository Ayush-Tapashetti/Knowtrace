"""Step 7: the model-backed feature still answers when the model fails; nothing private leaves or leaks."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from knowtrace.integrations.llm_client import (
    FakeLLMClient,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from tests.api.support import API, DESC, attempt, knows_unless_missing, make_client, probe_until_done
from tests.integrations.helpers import reply

KEY = "sk-ant-SENTINEL-must-never-appear-0123456789"
MODEL_ON: dict[str, Any] = {
    "deterministic_only": False,
    "llm_rephrase_enabled": True,
    "anthropic_api_key": KEY,
    "llm_max_retries": 0,  # no real sleeping in tests
}


def _open_lesson(c: TestClient, pseudonym: str | None = None) -> tuple[str, dict[str, Any], dict[str, Any]]:
    created = c.post(f"{API}/students", json={"pseudonym": pseudonym} if pseudonym else {}).json()
    sid = created["id"]
    for _ in range(2):
        for n in (1, 2, 3):
            attempt(c, sid, f"i.A.{n}", "a")
    d = probe_until_done(c, attempt(c, sid, "i.D.1", "b")["diagnosis"], knows_unless_missing({"B"}, DESC))
    assert d["state"] == "LESSON_ASSIGNED"
    return sid, d, c.get(f"{API}/lessons/{d['lesson_id']}").json()


# --- fallback assertions (every model failure mode) --------------------------------------------------
@pytest.mark.parametrize(
    "failure",
    [
        LLMTimeoutError("timeout"),
        LLMRateLimitError("rate limit"),
        LLMProviderError("500 from provider"),
        "this is not json at all",  # malformed output
        reply("Add."),  # well-formed but rejected by the guard
        reply("Fractions and Quantum Mechanics: add the tops."),  # names a concept outside the lesson
    ],
    ids=["timeout", "rate_limit", "provider_error", "malformed", "guard_length", "guard_foreign_concept"],
)
def test_lesson_still_valid_with_source_fallback_when_the_model_fails(
    seed_dir: Path, failure: str | LLMError
) -> None:
    llm = FakeLLMClient([failure])
    with make_client(seed_dir, llm=llm, **MODEL_ON) as c:
        _, _, lesson = _open_lesson(c)
    texts = [s for s in lesson["steps"] if s["text"]]
    assert texts, "lesson must still carry teaching text"
    assert {s["source"] for s in texts} == {"fallback"}
    assert all(s["text"].strip() for s in texts)
    assert sum(s["kind"] == "CHECK" for s in lesson["steps"]) >= 2  # P0-4 still holds on the fallback path
    assert lesson["est_seconds"] <= 300
    assert llm.calls, "the model really was tried"


def test_diagnosis_does_not_depend_on_the_model_at_all(seed_dir: Path) -> None:
    broken = FakeLLMClient([LLMTimeoutError("down")])
    with make_client(seed_dir) as plain, make_client(seed_dir, llm=broken, **MODEL_ON) as flaky:
        _, d_plain, _ = _open_lesson(plain)
        _, d_flaky, _ = _open_lesson(flaky)
    for k in ("root_concept_id", "verdict", "confidence", "probes_used"):
        assert d_plain[k] == d_flaky[k]


# --- PII masking before egress --------------------------------------------------------------------
def test_nothing_identifying_is_sent_to_the_provider(seed_dir: Path) -> None:
    llm = FakeLLMClient([reply("Add the tops when the bottoms match: 1/4 + 2/4 = 3/4.")])
    pseudonym = "priya.sharma.9876543210"
    with make_client(seed_dir, llm=llm, **MODEL_ON) as c:
        sid, d, _ = _open_lesson(c, pseudonym)
    assert llm.calls
    sent = "\n".join(system + "\n" + user for system, user in llm.calls)
    for secret in (pseudonym, "priya", "sharma", "9876543210", sid, d["id"], d["lesson_id"], KEY):
        assert secret not in sent, secret
    assert "@" not in sent and "http" not in sent


# --- secrets and internals never leak ------------------------------------------------------------------
def test_api_key_never_appears_in_logs_or_responses(seed_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    llm = FakeLLMClient([LLMProviderError("upstream provider error"), reply("ok")])
    bodies: list[str] = []
    with make_client(seed_dir, llm=llm, **MODEL_ON) as c:
        _open_lesson(c)
        for path in ("/status", "/health", "/concepts/nope", "/students/missing", "/items?limit=0"):
            bodies.append(c.get(f"{API}{path}").text)
        bodies.append(c.post(f"{API}/students", json={"pseudonym": "!!"}).text)
        bodies.append(c.delete(f"{API}/students/x").text)
    assert KEY not in caplog.text
    assert all(KEY not in b for b in bodies)


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/concepts/nope", None),
        ("get", "/students/missing", None),
        ("get", "/lessons/missing", None),
        ("get", "/items?limit=0", None),
        ("post", "/students", {"pseudonym": "!!"}),
        ("post", "/students", {"unexpected": 1}),
        ("post", "/diagnoses/missing/answer", {"answer": "a"}),
        ("delete", "/students/x", None),
    ],
)
def test_error_responses_use_the_envelope_and_show_no_internals(
    client: TestClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    r = client.request(method, f"{API}{path}", json=body)
    assert r.status_code >= 400
    text = r.text
    for marker in ("Traceback", 'File "', ".py", "sqlalchemy", "sqlite", "SELECT ", "/home/"):
        assert marker not in text, marker
    err = r.json()["error"]
    assert set(err) >= {"code", "message"}


def test_settings_repr_hides_the_key() -> None:
    from tests.api.support import make_settings

    s = make_settings(None, anthropic_api_key=KEY)
    assert KEY not in repr(s) and KEY not in str(s) and KEY not in s.model_dump_json()


def test_the_suite_really_blocks_outbound_connections() -> None:
    import socket

    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
        pytest.raises(RuntimeError, match="blocked"),
    ):
        sock.connect(("93.184.216.34", 80))
