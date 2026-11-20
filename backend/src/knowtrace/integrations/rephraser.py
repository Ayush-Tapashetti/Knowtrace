"""Optional model rewording of already-selected lesson text, with deterministic fallback.

Routing: disabled or no client -> authored text. Otherwise cache -> model (bounded retries with
jittered backoff) -> output guard. Any failure ends in the authored text, labelled with why.
Results say where they came from (`source`) so the UI and the evals can tell.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from knowtrace.core.settings import Settings
from knowtrace.integrations.cache import TTLCache, cache_key
from knowtrace.integrations.errors import LLMError, LLMProviderError, LLMRateLimitError, LLMTimeoutError
from knowtrace.integrations.llm_client import LLMClient
from knowtrace.integrations.output_guard import check_output, parse_output
from knowtrace.integrations.payload_mask import build_rephrase_payload
from knowtrace.integrations.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt

log = logging.getLogger("knowtrace.integrations.rephraser")

Source = Literal["model", "fallback", "cache"]


@dataclass(frozen=True, slots=True)
class RephraseResult:
    text: str
    source: Source
    reason: str | None = None  # why the fallback was used
    attempts: int = 0


@dataclass(frozen=True, slots=True)
class RephraserConfig:
    model: str
    prompt_version: str = PROMPT_VERSION
    timeout_s: float = 8.0
    max_retries: int = 1
    max_tokens: int = 600
    backoff_base_s: float = 0.5
    backoff_cap_s: float = 4.0
    min_ratio: float = 0.4
    max_ratio: float = 2.0

    @classmethod
    def from_settings(cls, s: Settings) -> RephraserConfig:
        return cls(model=s.llm_model, timeout_s=s.llm_timeout_seconds, max_retries=s.llm_max_retries)


def _reason(exc: LLMError) -> str:
    if isinstance(exc, LLMTimeoutError):
        return "timeout"
    if isinstance(exc, LLMRateLimitError):
        return "rate_limited"
    if isinstance(exc, LLMProviderError):
        return "provider_error"
    return "unavailable"


class Rephraser:
    def __init__(
        self,
        config: RephraserConfig,
        client: LLMClient | None,
        *,
        enabled: bool,
        concept_names: Mapping[str, str],
        cache: TTLCache | None = None,
        sleep: Callable[[float], None] = time.sleep,
        rng: random.Random | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._cfg, self._client, self._enabled = config, client, enabled
        self._names = dict(concept_names)
        self._cache = cache if cache is not None else TTLCache()
        self._sleep, self._rng, self._clock = sleep, rng or random.Random(), clock

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        concept_names: Mapping[str, str],
        *,
        client: LLMClient | None = None,
        cache: TTLCache | None = None,
    ) -> Rephraser:
        """Wire from config. The real client is only built when every gate is open (D3)."""
        if client is None and settings.llm_enabled:
            from knowtrace.integrations.llm_client import AnthropicClient

            key = settings.anthropic_api_key
            assert key is not None  # llm_enabled guarantees it
            client = AnthropicClient(key.get_secret_value(), settings.llm_model)
        return cls(
            RephraserConfig.from_settings(settings),
            client,
            enabled=settings.llm_enabled,
            concept_names=concept_names,
            cache=cache,
        )

    def rephrase(
        self,
        text: str,
        concept_id: str,
        lesson_concept_ids: Sequence[str],
        reading_level: str = "grade 8",
    ) -> RephraseResult:
        start = self._clock()
        result = self._route(text, concept_id, lesson_concept_ids, reading_level)
        # Structured, content-free: no text, no ids, no payload.
        log.info(
            "rephrase source=%s reason=%s attempts=%d latency_ms=%d",
            result.source,
            result.reason or "-",
            result.attempts,
            int((self._clock() - start) * 1000),
        )
        return result

    def _fallback(self, text: str, reason: str, attempts: int = 0) -> RephraseResult:
        return RephraseResult(text, "fallback", reason, attempts)

    def _route(
        self, text: str, concept_id: str, lesson_concept_ids: Sequence[str], reading_level: str
    ) -> RephraseResult:
        if not self._enabled or self._client is None:
            return self._fallback(text, "disabled")

        allowed = [self._names[c] for c in lesson_concept_ids if c in self._names]
        others = [n for c, n in self._names.items() if c not in set(lesson_concept_ids)]
        payload = build_rephrase_payload(
            text, self._names.get(concept_id, concept_id), allowed, reading_level
        )
        key = cache_key(payload, prompt_version=self._cfg.prompt_version, model=self._cfg.model)
        cached = self._cache.get(key)
        if cached is not None:
            return RephraseResult(cached, "cache")

        user = build_user_prompt(payload)
        reason = "unavailable"
        attempts = 1 + self._cfg.max_retries
        for attempt in range(attempts):
            try:
                raw = self._client.complete(
                    SYSTEM_PROMPT, user, max_tokens=self._cfg.max_tokens, timeout_s=self._cfg.timeout_s
                )
            except LLMError as exc:
                reason = _reason(exc)
                if not exc.retryable:
                    return self._fallback(text, reason, attempt + 1)
            else:
                parsed = parse_output(raw)
                if parsed is None:
                    reason = "invalid_output"
                else:
                    bad = check_output(
                        payload.text,
                        parsed,
                        allowed_names=allowed,
                        other_names=others,
                        min_ratio=self._cfg.min_ratio,
                        max_ratio=self._cfg.max_ratio,
                    )
                    if bad is None:
                        self._cache.put(key, parsed)
                        return RephraseResult(parsed, "model", None, attempt + 1)
                    reason = f"guard_rejected:{bad}"
            if attempt + 1 < attempts:
                self._sleep(self._backoff(attempt))
        return self._fallback(text, reason, attempts)

    def _backoff(self, attempt: int) -> float:
        base = min(self._cfg.backoff_cap_s, self._cfg.backoff_base_s * 2.0**attempt)
        return base * (0.5 + 0.5 * self._rng.random())  # jitter in [50%, 100%] of the step
