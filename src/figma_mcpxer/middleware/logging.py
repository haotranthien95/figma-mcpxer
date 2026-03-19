"""Structured request-logging middleware.

In development (LOG_FORMAT=text) the standard uvicorn access log is sufficient.
In production (LOG_FORMAT=json) this middleware emits one JSON log line per
request containing: request_id, method, path, status, duration_ms, client_ip.

NOTE: Implemented as a pure ASGI middleware (not BaseHTTPMiddleware) so that
SSE streaming connections are passed through without body-buffering interference.
For SSE connections the status is logged as 200 (assumed) since the response
headers arrive asynchronously through the streaming send channel.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any

logger = logging.getLogger("figma_mcpxer.access")

# Context variable so request_id is accessible from tool handlers in the same request
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestLoggingMiddleware:
    """Emit one structured log line per HTTP request.

    Pure ASGI middleware — does NOT inherit BaseHTTPMiddleware so it is
    compatible with long-lived SSE streaming responses.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        req_id = str(uuid.uuid4())[:8]
        request_id_var.set(req_id)

        method = scope.get("method", "")
        path = scope.get("path", "")
        client = scope.get("client")
        client_ip = client[0] if client else "-"

        start = time.perf_counter()
        status_holder: list[int] = [200]

        async def send_with_logging(message: Any) -> None:
            if message["type"] == "http.response.start":
                status_holder[0] = message.get("status", 200)
                # Inject request ID into response headers
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", req_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_logging)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.info(
                "request",
                extra={
                    "request_id": req_id,
                    "method": method,
                    "path": path,
                    "status": status_holder[0],
                    "duration_ms": duration_ms,
                    "client": client_ip,
                },
            )


def setup_json_logging(level: str = "INFO") -> None:
    """Configure the root logger to emit JSON lines.

    Call this once at startup when LOG_FORMAT=json.
    Regular text logging is handled by uvicorn's default config.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    # Replace any existing handlers added by uvicorn / basicConfig
    root.handlers = [handler]


class _JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter — avoids the json-logger dependency."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge any extra fields (e.g. from RequestLoggingMiddleware)
        for key, val in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                payload[key] = val

        req_id = request_id_var.get("")
        if req_id:
            payload["request_id"] = req_id

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload)
