"""MCP server with Streamable HTTP transport (MCP spec 2025-03-26).

Remote MCP clients (Claude Code, Claude Desktop, Cursor, custom agents) connect to:
  POST /mcp           — single MCP endpoint (initialize, tool calls, notifications)
  GET  /health        — liveness probe used by Docker and load balancers
  POST /webhooks/figma — receive Figma FILE_UPDATE events (Phase 8)
  GET  /metrics        — Prometheus text metrics (Phase 9)

The legacy SSE transport (/sse + /messages/) has been replaced by the
Streamable HTTP transport which uses a single POST endpoint and supports
both streaming SSE responses and plain JSON responses.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from figma_mcpxer import metrics  # noqa: F401 — registers Prometheus metrics on import
from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.config import Settings
from figma_mcpxer.exceptions import FigmaAPIError, MCPAuthError, ToolInputError
from figma_mcpxer.figma.client import FigmaClient
from figma_mcpxer.middleware.logging import RequestLoggingMiddleware, setup_json_logging
from figma_mcpxer.middleware.rate_limit import RateLimitMiddleware
from figma_mcpxer.tools import registry
from figma_mcpxer.webhooks.handler import WebhookEvent, handle_webhook_event, verify_passcode

logger = logging.getLogger(__name__)


def _create_cache(settings: Settings) -> CacheStore:
    """Return a CacheStore, switching to Redis when REDIS_URL is configured."""
    if settings.redis_url:
        from figma_mcpxer.cache.redis_store import RedisCacheStore  # lazy import
        logger.info("Using Redis cache: %s", settings.redis_url)
        return RedisCacheStore(settings.cache_ttl_seconds, settings.redis_url)  # type: ignore[return-value]
    return CacheStore(settings.cache_ttl_seconds)


def _build_mcp_server(
    figma_client: FigmaClient,
    cache_store: CacheStore,
) -> Server:
    """Create and configure the MCP server with all registered tools.

    Uses closures to inject figma_client and cache_store into tool handlers
    without global state.
    """
    mcp = Server("figma-mcpxer")

    @mcp.list_tools()
    async def list_tools() -> list[types.Tool]:
        return registry.get_all_tools()

    @mcp.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        start = time.perf_counter()
        status = "success"
        try:
            result = await registry.dispatch(name, arguments, figma_client, cache_store)
            return result
        except ToolInputError as exc:
            status = "error"
            return [types.TextContent(type="text", text=f"Tool input error: {exc}")]
        except FigmaAPIError as exc:
            status = "error"
            return [types.TextContent(type="text", text=f"Figma API error: {exc}")]
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            metrics.TOOL_CALLS.labels(tool=name, status=status).inc()
            metrics.TOOL_DURATION.labels(tool=name).observe(duration_ms)

    return mcp


def create_app(settings: Settings) -> Starlette:
    """Build the Starlette ASGI application.

    Owns the FigmaClient and CacheStore lifetimes — they are created once
    at startup and closed at shutdown.
    """
    if settings.log_format == "json":
        setup_json_logging(settings.log_level)

    figma_client = FigmaClient(
        access_token=settings.figma_access_token,
        base_url=settings.figma_api_base_url,
    )
    cache_store = _create_cache(settings)
    mcp_server = _build_mcp_server(figma_client, cache_store)
    session_manager = StreamableHTTPSessionManager(mcp_server)

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        logger.info("figma-mcpxer starting — %d tools registered", len(registry.get_all_tools()))
        async with session_manager.run():
            try:
                yield
            finally:
                await figma_client.close()
                logger.info("figma-mcpxer stopped")

    # ------------------------------------------------------------------ #
    # Route handlers                                                        #
    # ------------------------------------------------------------------ #

    async def handle_mcp(request: Request) -> Response:
        """Single MCP endpoint — handles initialize, tool calls, notifications."""
        if settings.mcp_auth_token:
            auth = request.headers.get("authorization", "")
            if auth != f"Bearer {settings.mcp_auth_token}":
                raise MCPAuthError()

        await session_manager.handle_request(
            request.scope, request.receive, request._send  # type: ignore[attr-defined]
        )
        return Response()  # response already sent via send

    async def health(_: Request) -> JSONResponse:
        tools = registry.get_all_tools()
        return JSONResponse(
            {"status": "ok", "version": "0.1.0", "tools_registered": len(tools)}
        )

    async def handle_figma_webhook(request: Request) -> JSONResponse:
        """Receive Figma webhook deliveries and invalidate the file cache."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "invalid JSON body"})

        try:
            event = WebhookEvent.model_validate(body)
        except ValidationError as exc:
            return JSONResponse(status_code=422, content={"error": str(exc)})

        if not verify_passcode(event.passcode, settings.figma_webhook_passcode):
            logger.warning("Rejected webhook delivery — passcode mismatch")
            return JSONResponse(status_code=403, content={"error": "invalid passcode"})

        summary = await handle_webhook_event(event, cache_store)
        return JSONResponse({"ok": True, **summary})

    async def prometheus_metrics(_: Request) -> Response:
        """Expose Prometheus metrics in the standard text format."""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    # ------------------------------------------------------------------ #
    # App assembly with middleware                                          #
    # ------------------------------------------------------------------ #

    app = Starlette(
        debug=settings.debug,
        lifespan=lifespan,
        routes=[
            Route("/health", health),
            Route("/mcp", handle_mcp, methods=["GET", "POST", "DELETE"]),
            Route("/webhooks/figma", handle_figma_webhook, methods=["POST"]),
            Route("/metrics", prometheus_metrics),
        ],
    )

    app.add_middleware(RequestLoggingMiddleware)
    if settings.rate_limit_rps > 0:
        app.add_middleware(RateLimitMiddleware, max_rps=settings.rate_limit_rps)

    return app
