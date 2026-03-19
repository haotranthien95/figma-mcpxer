from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from mcp import types

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.figma.client import FigmaClient

# ToolHandler signature: (arguments, client, cache) -> list[TextContent | ...]
ToolHandler = Callable[
    [dict[str, Any], FigmaClient, CacheStore],
    Coroutine[Any, Any, list[types.TextContent]],
]

_registry: dict[str, tuple[types.Tool, ToolHandler]] = {}


def register(tool: types.Tool, handler: ToolHandler) -> None:
    """Register a tool definition with its async handler."""
    _registry[tool.name] = (tool, handler)


def get_all_tools() -> list[types.Tool]:
    """Return all registered tool definitions for list_tools()."""
    return [tool for tool, _ in _registry.values()]


async def dispatch(
    name: str,
    arguments: dict[str, Any],
    client: FigmaClient,
    cache: CacheStore,
) -> list[types.TextContent]:
    """Route a call_tool() invocation to the correct handler."""
    if name not in _registry:
        raise ValueError(f"Unknown tool: {name!r}")
    _, handler = _registry[name]
    return await handler(arguments, client, cache)


def _load_all_tool_modules() -> None:
    """Import every tool module to trigger their register() calls.

    Add new tool modules here as phases are implemented.
    """
    from figma_mcpxer.tools import codegen as _p6  # noqa: F401
    from figma_mcpxer.tools import collaboration as _p7  # noqa: F401
    from figma_mcpxer.tools import components as _p4  # noqa: F401
    from figma_mcpxer.tools import file as _p2  # noqa: F401
    from figma_mcpxer.tools import layout as _p5  # noqa: F401
    from figma_mcpxer.tools import tokens as _p3  # noqa: F401
    from figma_mcpxer.tools import webhooks as _p8  # noqa: F401


_load_all_tool_modules()
