"""The model client interface, a real Anthropic implementation, and an in-memory fake."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol

from knowtrace.integrations.errors import (
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from knowtrace.integrations.payload_mask import mask_text

if TYPE_CHECKING:
    import httpx2  # the SDK's own HTTP stack; plain `httpx` clients are rejected by the SDK


class LLMClient(Protocol):
    def complete(self, system: str, user: str, *, max_tokens: int, timeout_s: float) -> str:
        """Return the model's text reply, or raise an `LLMError` subclass."""
        ...


class AnthropicClient:
    """Real client. Builds the SDK lazily, so the optional `anthropic` extra is only needed when
    this class is constructed. SDK retries are disabled: retry policy lives in the `Rephraser`."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str | None = None,
        http_client: httpx2.Client | None = None,
    ) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise LLMUnavailableError(
                "the 'anthropic' package is not installed (pip install .[llm])"
            ) from exc
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(
            api_key=api_key, base_url=base_url, http_client=http_client, max_retries=0
        )
        self._model = model

    def complete(self, system: str, user: str, *, max_tokens: int, timeout_s: float) -> str:
        a = self._anthropic
        # Last line of defence: even a caller that skipped the payload builder cannot leak.
        system, user = mask_text(system), mask_text(user)
        try:
            msg = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                timeout=timeout_s,
            )
        except a.APITimeoutError as exc:  # subclass of APIConnectionError, so it must come first
            raise LLMTimeoutError("model call timed out") from exc
        except a.RateLimitError as exc:
            raise LLMRateLimitError("model rate limit") from exc
        except a.APIStatusError as exc:
            raise LLMProviderError(f"model returned HTTP {exc.status_code}", status=exc.status_code) from exc
        except a.APIConnectionError as exc:
            raise LLMProviderError("could not reach the model API", retryable=True) from exc
        return "".join(b.text for b in msg.content if isinstance(b, a.types.TextBlock))


class FakeLLMClient:
    """Scripted client for tests. Each item is a reply string (returned) or an exception (raised).
    When the script runs out, the last item repeats."""

    def __init__(self, script: Iterable[str | LLMError]) -> None:
        self._script = list(script)
        if not self._script:
            raise ValueError("script must not be empty")
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, *, max_tokens: int, timeout_s: float) -> str:
        self.calls.append((system, user))
        item = self._script[min(len(self.calls), len(self._script)) - 1]
        if isinstance(item, Exception):
            raise item
        return item
