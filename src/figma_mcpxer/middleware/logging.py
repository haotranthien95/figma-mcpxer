"""Structured request-logging middleware.

In development (LOG_FORMAT=text) the standard uvicorn access log is sufficient.
In production (LOG_FORMAT=json) this middleware emits one JSON log line per
request containing: request_id, method, path, status, duration_ms, client_ip.

Attach to the Starlette app via:
    app.add_middleware(RequestLoggingMiddleware)
"""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("figma_mcpxer.access")

# Context variable so request_id is accessible from tool handlers in the same request
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Emit one structured log line per HTTP request."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        req_id = str(uuid.uuid4())[:8]
        request_id_var.set(req_id)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        logger.info(
            "request",
            extra={
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "client": request.client.host if request.client else "-",
            },
        )
        response.headers["X-Request-Id"] = req_id
        return response


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
