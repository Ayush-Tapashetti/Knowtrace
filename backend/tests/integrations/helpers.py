"""Shared fixtures for integration tests: a tiny concept-name map and a ready-made Rephraser."""

from __future__ import annotations

import json
import random

from knowtrace.integrations.cache import TTLCache
from knowtrace.integrations.llm_client import LLMClient
from knowtrace.integrations.rephraser import Rephraser, RephraserConfig

NAMES = {
    "A": "Counting",
    "B": "Fractions",
    "C": "Adding fractions",
    "D": "Ratios",
    "E": "Equivalent fractions",
    "F": "Mixed numbers",
}
LESSON = ["B", "C"]  # concepts this lesson may mention
ORIGINAL = "To add fractions with the same denominator, add the tops: 1/4 + 2/4 = 3/4."
GOOD = "When two fractions share a denominator, just add the numerators: 1/4 + 2/4 = 3/4."


def reply(text: str) -> str:
    return json.dumps({"text": text})


class Recorder:
    """Records sleeps so retry/backoff behaviour is observable without waiting."""

    def __init__(self) -> None:
        self.sleeps: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def make(
    client: LLMClient | None,
    *,
    enabled: bool = True,
    max_retries: int = 1,
    cache: TTLCache | None = None,
    sleeper: Recorder | None = None,
    model: str = "test-model",
    prompt_version: str = "rephrase-v1",
) -> Rephraser:
    cfg = RephraserConfig(model=model, max_retries=max_retries, prompt_version=prompt_version)
    return Rephraser(
        cfg,
        client,
        enabled=enabled,
        concept_names=NAMES,
        cache=cache,
        sleep=sleeper or Recorder(),
        rng=random.Random(0),
    )
