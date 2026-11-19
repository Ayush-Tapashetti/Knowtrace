"""In-process per-client token bucket (no extra dependency). Good enough for a single-process demo."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass

from starlette.types import ASGIApp, Receive, Scope, Send


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimitMiddleware:
    """Allows `per_minute` requests per client address, refilled continuously. Exempts /health."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        per_minute: int,
        clock: Callable[[], float] = time.monotonic,
        max_clients: int = 10_000,
    ) -> None:
        self.app, self.capacity, self.clock, self.max_clients = app, float(per_minute), clock, max_clients
        self.rate = per_minute / 60.0
        self.buckets: dict[str, _Bucket] = {}

    def _take(self, key: str) -> float:
        """Return 0.0 when allowed, else seconds until a token is available."""
        now = self.clock()
        b = self.buckets.get(key)
        if b is None:
            if len(self.buckets) >= self.max_clients:  # bound memory: drop the oldest entry
                self.buckets.pop(next(iter(self.buckets)))
            b = self.buckets[key] = _Bucket(self.capacity, now)
        b.tokens = min(self.capacity, b.tokens + (now - b.updated) * self.rate)
        b.updated = now
        if b.tokens >= 1.0:
            b.tokens -= 1.0
            return 0.0
        return (1.0 - b.tokens) / self.rate

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] == "OPTIONS" or scope["path"] == "/health":
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        wait = self._take(client[0] if client else "unknown")
        if wait == 0.0:
            await self.app(scope, receive, send)
            return
        body = json.dumps(
            {"error": {"code": "rate_limited", "message": "Too many requests; slow down.", "details": None}}
        )
        retry = str(max(1, int(wait + 0.999)))
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [(b"content-type", b"application/json"), (b"retry-after", retry.encode())],
            }
        )
        await send({"type": "http.response.body", "body": body.encode()})
