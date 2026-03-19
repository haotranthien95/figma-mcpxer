"""MCP server with HTTP + SSE transport.

Remote MCP clients (Claude Desktop, Cursor, custom agents) connect to:
  GET  /sse      — open SSE stream for MCP handshake and server-push
  POST /messages — send MCP tool call messages
  GET  /health   — liveness probe used by Docker and load balancers
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.config import Settings
from figma_mcpxer.exceptions import FigmaAPIError, MCPAuthError, ToolInputError
from figma_mcpxer.figma.client import FigmaClient
from figma_mcpxer.tools import registry

logger = logging.getLogger(__name__)


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
        try:
            return await registry.dispatch(name, arguments, figma_client, cache_store)
        except ToolInputError as exc:
            return [types.TextContent(type="text", text=f"Tool input error: {exc}")]
        except FigmaAPIError as exc:
            return [types.TextContent(type="text", text=f"Figma API error: {exc}")]

    return mcp


def create_app(settings: Settings) -> Starlette:
    """Build the Starlette ASGI application.

    Owns the FigmaClient and CacheStore lifetimes — they are created once
    at startup and closed at shutdown.
    """
    figma_client = FigmaClient(
        access_token=settings.figma_access_token,
        base_url=settings.figma_api_base_url,
    )
    cache_store = CacheStore(ttl_seconds=settings.cache_ttl_seconds)
    mcp_server = _build_mcp_server(figma_client, cache_store)
    transport = SseServerTransport("/messages/")

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        logger.info("figma-mcpxer starting — %d tools registered", len(registry.get_all_tools()))
        try:
            yield
        finally:
            await figma_client.close()
            logger.info("figma-mcpxer stopped")

    async def handle_sse(request: Request) -> Response:
        """SSE endpoint — MCP clients connect here first."""
        if settings.mcp_auth_token:
            auth = request.headers.get("authorization", "")
            if auth != f"Bearer {settings.mcp_auth_token}":
                raise MCPAuthError()

        async with transport.connect_sse(
            request.scope, request.receive, request._send  # type: ignore[attr-defined]
        ) as streams:
            await mcp_server.run(
                streams[0],
                streams[1],
                mcp_server.create_initialization_options(),
            )
        return Response()  # unreachable — SSE stream never returns normally

    async def health(_: Request) -> JSONResponse:
        tools = registry.get_all_tools()
        return JSONResponse(
            {"status": "ok", "version": "0.1.0", "tools_registered": len(tools)}
        )

    return Starlette(
        debug=settings.debug,
        lifespan=lifespan,
        routes=[
            Route("/health", health),
            Route("/sse", handle_sse),
            Mount("/messages/", app=transport.handle_post_message),
        ],
    )
