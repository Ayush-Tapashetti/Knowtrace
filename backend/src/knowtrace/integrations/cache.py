"""Small in-process TTL + LRU cache for validated model output.

Key = sha256(masked input, concept, reading level, allowed concepts, prompt version, model id), so
changing the prompt version or the model invalidates old entries by construction. Only validated
model replies are stored, never fallbacks. TTL and size are bounded; `clear()` is the manual reset.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Callable

from knowtrace.integrations.payload_mask import RephrasePayload


def cache_key(payload: RephrasePayload, *, prompt_version: str, model: str) -> str:
    blob = json.dumps(
        [
            payload.text,
            payload.concept_name,
            payload.reading_level,
            payload.allowed_concepts,
            prompt_version,
            model,
        ],
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class TTLCache:
    def __init__(
        self,
        *,
        max_entries: int = 512,
        ttl_seconds: float = 86_400.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max, self._ttl, self._clock = max_entries, ttl_seconds, clock
        self._data: OrderedDict[str, tuple[float, str]] = OrderedDict()

    def get(self, key: str) -> str | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if self._clock() - stored_at >= self._ttl:
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return value

    def put(self, key: str, value: str) -> None:
        self._data[key] = (self._clock(), value)
        self._data.move_to_end(key)
        while len(self._data) > self._max:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)
