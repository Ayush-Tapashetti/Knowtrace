from __future__ import annotations

import logging

import pytest

from knowtrace.core.settings import Settings
from knowtrace.integrations.cache import TTLCache
from knowtrace.integrations.errors import (
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from knowtrace.integrations.llm_client import FakeLLMClient
from knowtrace.integrations.rephraser import Rephraser
from tests.integrations.helpers import GOOD, LESSON, NAMES, ORIGINAL, Recorder, make, reply


def run(r: Rephraser, text: str = ORIGINAL):
    return r.rephrase(text, "C", LESSON)


def test_success_comes_from_the_model_and_is_labelled() -> None:
    client = FakeLLMClient([reply(GOOD)])
    res = run(make(client))
    assert (res.text, res.source, res.reason, res.attempts) == (GOOD, "model", None, 1)
    assert len(client.calls) == 1


def test_second_identical_request_is_a_cache_hit() -> None:
    client = FakeLLMClient([reply(GOOD)])
    r = make(client)
    assert run(r).source == "model"
    again = run(r)
    assert (again.text, again.source) == (GOOD, "cache")
    assert len(client.calls) == 1  # no second model call


def test_disabled_or_missing_client_returns_authored_text_without_any_call() -> None:
    client = FakeLLMClient([reply(GOOD)])
    off = run(make(client, enabled=False))
    assert (off.text, off.source, off.reason) == (ORIGINAL, "fallback", "disabled")
    assert client.calls == []
    assert run(make(None)).reason == "disabled"


def test_timeout_is_retried_then_succeeds() -> None:
    sleeper = Recorder()
    client = FakeLLMClient([LLMTimeoutError("t"), reply(GOOD)])
    res = run(make(client, sleeper=sleeper))
    assert res.source == "model" and res.attempts == 2 and len(client.calls) == 2
    assert len(sleeper.sleeps) == 1 and 0.25 <= sleeper.sleeps[0] <= 0.5  # base 0.5 with 50-100% jitter


def test_persistent_failures_fall_back_after_bounded_attempts() -> None:
    for exc, reason in [
        (LLMTimeoutError("t"), "timeout"),
        (LLMRateLimitError("r"), "rate_limited"),
        (LLMProviderError("p", status=503), "provider_error"),
    ]:
        sleeper = Recorder()
        client = FakeLLMClient([exc])
        res = run(make(client, max_retries=2, sleeper=sleeper))
        assert (res.text, res.source, res.reason, res.attempts) == (ORIGINAL, "fallback", reason, 3)
        assert len(client.calls) == 3 and len(sleeper.sleeps) == 2  # never sleeps after the last try
        assert (
            sleeper.sleeps[1] > sleeper.sleeps[0] * 0.9 or sleeper.sleeps[1] >= 0.5
        )  # backoff grows (with jitter)


def test_backoff_is_capped() -> None:
    sleeper = Recorder()
    run(make(FakeLLMClient([LLMTimeoutError("t")]), max_retries=8, sleeper=sleeper))
    assert len(sleeper.sleeps) == 8 and max(sleeper.sleeps) <= 4.0


def test_non_retryable_provider_error_is_not_retried() -> None:
    sleeper = Recorder()
    client = FakeLLMClient([LLMProviderError("bad key", status=401)])
    res = run(make(client, sleeper=sleeper))
    assert (res.source, res.reason, res.attempts) == ("fallback", "provider_error", 1)
    assert len(client.calls) == 1 and sleeper.sleeps == []


def test_malformed_output_is_retried_then_falls_back_and_is_never_passed_through() -> None:
    client = FakeLLMClient(["Sure! Here you go: " + GOOD])
    res = run(make(client))
    assert (res.text, res.source, res.reason) == (ORIGINAL, "fallback", "invalid_output")
    assert len(client.calls) == 2  # retry-then-fallback


def test_malformed_then_valid_recovers() -> None:
    res = run(make(FakeLLMClient(["nope", reply(GOOD)])))
    assert res.source == "model" and res.attempts == 2


@pytest.mark.parametrize(
    ("bad", "reason"),
    [
        ("To add fractions, add the tops: 1/4 + 2/4 = 5/4.", "guard_rejected:numbers_changed"),
        (
            "Using equivalent fractions, add the tops of 1/4 + 2/4 = 3/4 now.",
            "guard_rejected:foreign_concept",
        ),
        (
            "See https://x.example: 1/4 + 2/4 = 3/4 and add the tops of same denominators.",
            "guard_rejected:markup",
        ),
        ("Add.", "guard_rejected:length_ratio"),
    ],
)
def test_guard_rejections_fall_back_with_the_reason(bad: str, reason: str) -> None:
    res = run(make(FakeLLMClient([reply(bad)])))
    assert (res.text, res.source, res.reason) == (ORIGINAL, "fallback", reason)


def test_fallbacks_are_never_cached() -> None:
    cache = TTLCache()
    run(make(FakeLLMClient([LLMTimeoutError("t")]), cache=cache))
    assert len(cache) == 0
    run(make(FakeLLMClient([reply("Add.")]), cache=cache))  # guard-rejected reply
    assert len(cache) == 0


def test_changing_model_or_prompt_version_invalidates_the_cache() -> None:
    cache = TTLCache()
    first = FakeLLMClient([reply(GOOD)])
    run(make(first, cache=cache))
    for kw in ({"model": "other-model"}, {"prompt_version": "rephrase-v2"}):
        c = FakeLLMClient([reply(GOOD)])
        res = run(make(c, cache=cache, **kw))  # type: ignore[arg-type]
        assert res.source == "model" and len(c.calls) == 1, kw


def test_the_prompt_sent_to_the_client_is_built_from_the_masked_payload_only() -> None:
    client = FakeLLMClient([reply(GOOD)])
    text = ORIGINAL + " Ask student-7f3a (kid@school.example) about it."
    run(make(client), text)
    system, user = client.calls[0]
    assert "[student]" in user and "[email]" in user
    assert "student-7f3a" not in user + system and "kid@school.example" not in user + system
    assert "Allowed concepts: Adding fractions; Fractions" in user  # sorted allowlist
    assert "Ratios" not in user  # concepts outside the lesson are not even mentioned


def test_unknown_concept_ids_do_not_crash() -> None:
    client = FakeLLMClient([reply(GOOD)])
    res = make(client).rephrase(ORIGINAL, "ZZ", ["ZZ"])
    assert res.source in {"model", "fallback"}


def test_logs_are_structured_and_contain_no_content(caplog: pytest.LogCaptureFixture) -> None:
    text = ORIGINAL + " (student-7f3a, kid@school.example)"
    with caplog.at_level(logging.INFO, logger="knowtrace.integrations"):
        run(make(FakeLLMClient([reply(GOOD)])), text)
        run(make(FakeLLMClient([LLMTimeoutError("t")])), text)
    lines = [r.getMessage() for r in caplog.records]
    assert len(lines) == 2
    assert lines[0].startswith("rephrase source=model") and "attempts=1" in lines[0]
    assert "source=fallback reason=timeout" in lines[1]
    blob = "\n".join(lines)
    for secret in ("student-7f3a", "kid@school.example", "denominator", "1/4"):
        assert secret not in blob


def test_from_settings_respects_every_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_REPHRASE_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "placeholder-not-a-real-key")
    client = FakeLLMClient([reply(GOOD)])

    locked = Settings(_env_file=None)  # DETERMINISTIC_ONLY defaults to true
    assert run(Rephraser.from_settings(locked, NAMES, client=client)).reason == "disabled"
    assert client.calls == []

    monkeypatch.setenv("DETERMINISTIC_ONLY", "false")
    opened = Settings(_env_file=None)
    assert run(Rephraser.from_settings(opened, NAMES, client=client)).source == "model"

    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    keyless = Settings(_env_file=None)
    assert run(Rephraser.from_settings(keyless, NAMES, client=client)).reason == "disabled"
