"""In-memory sliding-window rate limiter middleware.

Limits requests per second per client IP. Suitable for a single-instance
deployment. For multi-replica setups, replace with a Redis-backed limiter
(e.g. slowapi + Redis backend) or an upstream proxy rate limit (nginx).

Configuration: set RATE_LIMIT_RPS in the environment (0 = disabled).

NOTE: Implemented as a pure ASGI middleware (not BaseHTTPMiddleware) so that
SSE streaming connections are passed through without body-buffering interference.
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    """Sliding-window rate limiter keyed by client IP.

    Tracks the timestamps of the last `max_rps` requests per IP.
    Rejects requests that would exceed the limit with HTTP 429.

    Pure ASGI middleware — does NOT inherit BaseHTTPMiddleware so it is
    compatible with long-lived SSE streaming responses.
    """

    def __init__(self, app: Any, *, max_rps: int = 60) -> None:
        self.app = app
        self._max_rps = max_rps
        # IP → deque of request timestamps (monotonic, in seconds)
        self._windows: dict[str, deque[float]] = {}

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or self._max_rps <= 0:
            await self.app(scope, receive, send)
            return

        client_ip = self._get_client_ip(scope)
        if not self._allow(client_ip):
            path = scope.get("path", "")
            logger.warning("Rate limit exceeded for %s on %s", client_ip, path)
            await self._send_429(send)
            return

        await self.app(scope, receive, send)

    def _allow(self, client_ip: str) -> bool:
        """Return True if the request is within the rate limit window."""
        now = time.monotonic()
        window_start = now - 1.0  # 1-second sliding window

        if client_ip not in self._windows:
            self._windows[client_ip] = deque()

        bucket = self._windows[client_ip]

        # Evict timestamps older than the window
        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= self._max_rps:
            return False

        bucket.append(now)
        return True

    @staticmethod
    def _get_client_ip(scope: Any) -> str:
        """Extract client IP, respecting X-Forwarded-For from trusted proxies."""
        headers = dict(scope.get("headers", []))
        forwarded = headers.get(b"x-forwarded-for", b"").decode()
        if forwarded:
            return forwarded.split(",")[0].strip()
        client = scope.get("client")
        return client[0] if client else "unknown"

    @staticmethod
    async def _send_429(send: Any) -> None:
        body = json.dumps(
            {
                "error": "rate_limit_exceeded",
                "detail": "Maximum requests/second exceeded.",
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
