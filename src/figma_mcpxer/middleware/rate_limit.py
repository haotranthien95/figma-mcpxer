"""In-memory sliding-window rate limiter middleware.

Limits requests per second per client IP. Suitable for a single-instance
deployment. For multi-replica setups, replace with a Redis-backed limiter
(e.g. slowapi + Redis backend) or an upstream proxy rate limit (nginx).

Configuration: set RATE_LIMIT_RPS in the environment (0 = disabled).
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter keyed by client IP.

    Tracks the timestamps of the last `max_rps` requests per IP.
    Rejects requests that would exceed the limit with HTTP 429.
    """

    def __init__(self, app: Any, *, max_rps: int = 60) -> None:
        super().__init__(app)
        self._max_rps = max_rps
        # IP → deque of request timestamps (monotonic, in seconds)
        self._windows: dict[str, deque[float]] = {}

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if self._max_rps <= 0:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        if not self._allow(client_ip):
            logger.warning("Rate limit exceeded for %s on %s", client_ip, request.url.path)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "detail": f"Maximum {self._max_rps} requests/second exceeded.",
                },
            )
        return await call_next(request)

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
    def _get_client_ip(request: Request) -> str:
        """Extract client IP, respecting X-Forwarded-For from trusted proxies."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
