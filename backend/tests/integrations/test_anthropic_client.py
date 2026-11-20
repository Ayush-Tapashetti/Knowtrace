"""The real client against an HTTP-level mock (no real network). The Anthropic SDK ships its own
`httpx2` stack and rejects plain `httpx` clients, so the mock transport comes from `httpx2`."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx2
import pytest

from knowtrace.integrations.errors import (
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from knowtrace.integrations.llm_client import AnthropicClient
from knowtrace.integrations.rephraser import Rephraser, RephraserConfig
from tests.integrations.helpers import GOOD, LESSON, NAMES, ORIGINAL, Recorder, reply

API_KEY = "placeholder-not-a-real-key"
Handler = Callable[[httpx2.Request], httpx2.Response]


def message(text: str) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "test-model",
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )


def error(status: int, kind: str) -> httpx2.Response:
    return httpx2.Response(status, json={"type": "error", "error": {"type": kind, "message": "boom"}})


class Server:
    """Records every request body and answers from a script of responses / exceptions."""

    def __init__(self, *script: httpx2.Response | Exception) -> None:
        self.script, self.requests = list(script), []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        item = self.script[min(len(self.requests), len(self.script)) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    def body(self, i: int = 0) -> str:
        return self.requests[i].content.decode()


def client_for(handler: Handler) -> AnthropicClient:
    http = httpx2.Client(transport=httpx2.MockTransport(handler))
    return AnthropicClient(API_KEY, "test-model", base_url="https://api.test", http_client=http)


def complete(c: AnthropicClient, user: str = "hi", system: str = "sys") -> str:
    return c.complete(system, user, max_tokens=50, timeout_s=3.0)


def test_success_returns_text_and_sends_a_well_formed_request() -> None:
    server = Server(message("hello there"))
    assert complete(client_for(server)) == "hello there"
    req = server.requests[0]
    assert req.method == "POST" and req.url.path == "/v1/messages"
    sent = json.loads(server.body())
    assert sent["model"] == "test-model" and sent["max_tokens"] == 50 and sent["system"] == "sys"
    assert sent["messages"] == [{"role": "user", "content": "hi"}]
    header_values = "".join(req.headers.get(h, "") for h in ("authorization", "x-api-key"))
    assert API_KEY in header_values  # the key travels in a header...
    assert API_KEY not in server.body()  # ...and never in the body


def test_sdk_retries_are_disabled_so_policy_lives_in_one_place() -> None:
    server = Server(error(500, "api_error"))
    with pytest.raises(LLMProviderError):
        complete(client_for(server))
    assert len(server.requests) == 1


@pytest.mark.parametrize(
    ("response", "exc", "retryable"),
    [
        (httpx2.ReadTimeout("slow"), LLMTimeoutError, True),
        (error(429, "rate_limit_error"), LLMRateLimitError, True),
        (error(500, "api_error"), LLMProviderError, True),
        (error(529, "overloaded_error"), LLMProviderError, True),
        (error(401, "authentication_error"), LLMProviderError, False),
        (error(400, "invalid_request_error"), LLMProviderError, False),
        (httpx2.ConnectError("no route"), LLMProviderError, True),
    ],
)
def test_failures_map_to_typed_errors(
    response: httpx2.Response | Exception, exc: type[Exception], retryable: bool
) -> None:
    with pytest.raises(exc) as info:
        complete(client_for(Server(response)))
    assert info.value.retryable is retryable  # type: ignore[attr-defined]


def test_pii_never_reaches_the_wire_even_if_a_caller_skips_the_payload_builder() -> None:
    server = Server(message("ok"))
    pii_system = "You help student-7f3a (mail kid@school.example, roll 21ABC1234)."
    pii_user = (
        "Call +91 98765 43210 or see https://school.example/u/42. id 123e4567-e89b-12d3-a456-426614174000"
    )
    complete(client_for(server), user=pii_user, system=pii_system)
    wire = server.body()
    for secret in (
        "student-7f3a",
        "kid@school.example",
        "21ABC1234",
        "98765 43210",
        "school.example",
        "123e4567",
    ):
        assert secret not in wire, secret
    for placeholder in ("[student]", "[email]", "[id]", "[number]", "[link]"):
        assert placeholder in wire, placeholder


def test_end_to_end_rephraser_over_http_masks_and_succeeds() -> None:
    server = Server(message(reply(GOOD)))
    r = Rephraser(
        RephraserConfig(model="test-model"),
        client_for(server),
        enabled=True,
        concept_names=NAMES,
        sleep=Recorder(),
    )
    res = r.rephrase(ORIGINAL + " Ask student-7f3a (kid@school.example).", "C", LESSON)
    assert res.source == "model" and res.text == GOOD
    wire = server.body()
    assert "student-7f3a" not in wire and "kid@school.example" not in wire
    assert "Allowed concepts: Adding fractions; Fractions" in json.loads(wire)["messages"][0]["content"]


def test_end_to_end_retry_after_a_server_error_then_success() -> None:
    server = Server(error(500, "api_error"), message(reply(GOOD)))
    sleeper = Recorder()
    r = Rephraser(
        RephraserConfig(model="test-model"),
        client_for(server),
        enabled=True,
        concept_names=NAMES,
        sleep=sleeper,
    )
    res = r.rephrase(ORIGINAL, "C", LESSON)
    assert (
        (res.source, res.attempts) == ("model", 2) and len(server.requests) == 2 and len(sleeper.sleeps) == 1
    )


@pytest.mark.parametrize(
    ("script", "reason"),
    [
        ([httpx2.ReadTimeout("slow")], "timeout"),
        ([error(429, "rate_limit_error")], "rate_limited"),
        ([error(401, "authentication_error")], "provider_error"),
        ([message("not json at all")], "invalid_output"),
        (
            [
                httpx2.Response(
                    200,
                    json={
                        "id": "m",
                        "type": "message",
                        "role": "assistant",
                        "model": "t",
                        "content": [],
                        "stop_reason": "end_turn",
                        "stop_sequence": None,
                        "usage": {"input_tokens": 1, "output_tokens": 0},
                    },
                )
            ],
            "invalid_output",
        ),
    ],
)
def test_end_to_end_every_failure_ends_in_the_authored_text(
    script: list[httpx2.Response | Exception], reason: str
) -> None:
    r = Rephraser(
        RephraserConfig(model="test-model"),
        client_for(Server(*script)),
        enabled=True,
        concept_names=NAMES,
        sleep=Recorder(),
    )
    res = r.rephrase(ORIGINAL, "C", LESSON)
    assert (res.text, res.source, res.reason) == (ORIGINAL, "fallback", reason)
