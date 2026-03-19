"""Phase 2 — File & Node Tools.

Provides MCP tools for reading Figma file structure and individual nodes.
All tools cache Figma API responses to reduce latency and rate-limit exposure.
"""

from __future__ import annotations

import json
from typing import Any

from mcp import types

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.exceptions import ToolInputError
from figma_mcpxer.figma.client import FigmaClient
from figma_mcpxer.figma.models import FigmaFile, FigmaFileNodes
from figma_mcpxer.tools.registry import register
from figma_mcpxer.utils.url import extract_file_key, normalize_node_id

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]


async def _fetch_file(
    file_key: str,
    client: FigmaClient,
    cache: CacheStore,
    *,
    depth: int | None = None,
) -> dict[str, Any]:
    cache_key = f"file:{file_key}:depth:{depth}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    data = await client.get_file(file_key, depth=depth)
    await cache.set(cache_key, data)
    return data  # type: ignore[return-value]


def _summarize_node(node: dict[str, Any], current_depth: int, max_depth: int) -> dict[str, Any]:
    """Recursively summarize a node tree, stopping at max_depth."""
    summary: dict[str, Any] = {
        "id": node.get("id"),
        "name": node.get("name"),
        "type": node.get("type"),
    }
    bbox = node.get("absoluteBoundingBox")
    if bbox:
        summary["bounds"] = bbox
    children = node.get("children", [])
    if children and current_depth < max_depth:
        summary["children"] = [
            _summarize_node(child, current_depth + 1, max_depth) for child in children
        ]
    elif children:
        summary["child_count"] = len(children)
    return summary


def _search_nodes(
    node: dict[str, Any],
    *,
    name_filter: str | None,
    type_filter: str | None,
    path: str,
    results: list[dict[str, Any]],
    limit: int,
) -> None:
    """Iterative DFS over the node tree to find matching nodes."""
    stack = [(node, path)]
    while stack and len(results) < limit:
        current, current_path = stack.pop()
        node_name = current.get("name", "")
        node_type = current.get("type", "")
        node_path = f"{current_path}/{node_name}"

        name_match = name_filter is None or name_filter.lower() in node_name.lower()
        type_match = type_filter is None or type_filter.upper() == node_type.upper()

        if name_match and type_match and node_type not in ("DOCUMENT",):
            results.append(
                {
                    "id": current.get("id"),
                    "name": node_name,
                    "type": node_type,
                    "path": node_path,
                }
            )

        for child in reversed(current.get("children", []) or []):
            stack.append((child, node_path))


# ---------------------------------------------------------------------------
# Tool: figma_get_file
# ---------------------------------------------------------------------------

_GET_FILE_TOOL = types.Tool(
    name="figma_get_file",
    description=(
        "Fetch a Figma file and return its structure: name, pages, and a node tree "
        "up to the specified depth. Use this to explore a design before drilling into "
        "specific nodes. Accepts a file key or full figma.com URL."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "file_key": {
                "type": "string",
                "description": (
                    "Figma file key or full figma.com URL. "
                    "Example: 'AbCdEfGh' or 'https://www.figma.com/design/AbCdEfGh/...'"
                ),
            },
            "depth": {
                "type": "integer",
                "description": (
                    "Node tree depth to return. Default 2 (pages + top-level frames). "
                    "Increase for deeper inspection (higher values mean larger responses)."
                ),
                "default": 2,
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": ["file_key"],
        "additionalProperties": False,
    },
)


async def _handle_get_file(
    arguments: dict[str, Any],
    client: FigmaClient,
    cache: CacheStore,
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    depth: int = arguments.get("depth", 2)

    raw = await _fetch_file(file_key, client, cache, depth=depth)
    figma_file = FigmaFile.model_validate(raw)

    result = {
        "name": figma_file.name,
        "version": figma_file.version,
        "last_modified": figma_file.last_modified,
        "component_count": len(figma_file.components),
        "style_count": len(figma_file.styles),
        "tree": _summarize_node(raw["document"], current_depth=0, max_depth=depth),
    }
    return _text(result)


register(_GET_FILE_TOOL, _handle_get_file)


# ---------------------------------------------------------------------------
# Tool: figma_list_pages
# ---------------------------------------------------------------------------

_LIST_PAGES_TOOL = types.Tool(
    name="figma_list_pages",
    description=(
        "List all pages in a Figma file with their IDs, names, and top-level child counts. "
        "Use this first to discover pages before fetching specific content."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "file_key": {
                "type": "string",
                "description": "Figma file key or URL.",
            },
        },
        "required": ["file_key"],
        "additionalProperties": False,
    },
)


async def _handle_list_pages(
    arguments: dict[str, Any],
    client: FigmaClient,
    cache: CacheStore,
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    # depth=1 returns document + pages only — minimises response size
    raw = await _fetch_file(file_key, client, cache, depth=1)
    figma_file = FigmaFile.model_validate(raw)

    pages = [
        {
            "id": page.id,
            "name": page.name,
            "child_count": page.child_count(),
        }
        for page in (figma_file.document.children or [])
        if page.type == "CANVAS"
    ]
    return _text({"file_name": figma_file.name, "pages": pages})


register(_LIST_PAGES_TOOL, _handle_list_pages)


# ---------------------------------------------------------------------------
# Tool: figma_get_node
# ---------------------------------------------------------------------------

_GET_NODE_TOOL = types.Tool(
    name="figma_get_node",
    description=(
        "Fetch a single Figma node by ID with all its properties. "
        "Returns the full node data including layout, styles, fills, and children. "
        "Use this to inspect a specific component, frame, or element."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "file_key": {
                "type": "string",
                "description": "Figma file key or URL.",
            },
            "node_id": {
                "type": "string",
                "description": (
                    "Node ID in '1234:5678' or '1234-5678' format. "
                    "Find IDs via figma_get_file or figma_list_pages."
                ),
            },
        },
        "required": ["file_key", "node_id"],
        "additionalProperties": False,
    },
)


async def _handle_get_node(
    arguments: dict[str, Any],
    client: FigmaClient,
    cache: CacheStore,
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    node_id = normalize_node_id(arguments["node_id"])

    cache_key = f"nodes:{file_key}:{node_id}"
    raw = await cache.get(cache_key)
    if raw is None:
        raw = await client.get_file_nodes(file_key, [node_id])
        await cache.set(cache_key, raw)

    response = FigmaFileNodes.model_validate(raw)
    node_data = response.nodes.get(node_id)
    if node_data is None:
        raise ToolInputError(f"Node {node_id!r} not found in file {file_key!r}")

    return _text({"file_name": response.name, "node": node_data.get("document")})


register(_GET_NODE_TOOL, _handle_get_node)


# ---------------------------------------------------------------------------
# Tool: figma_get_nodes
# ---------------------------------------------------------------------------

_GET_NODES_TOOL = types.Tool(
    name="figma_get_nodes",
    description=(
        "Fetch multiple Figma nodes in a single API call. "
        "More efficient than calling figma_get_node repeatedly. "
        "Returns a map of node_id → node data."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "file_key": {
                "type": "string",
                "description": "Figma file key or URL.",
            },
            "node_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of node IDs to fetch (e.g. ['1234:5678', '2:4']).",
                "minItems": 1,
                "maxItems": 50,
            },
        },
        "required": ["file_key", "node_ids"],
        "additionalProperties": False,
    },
)


async def _handle_get_nodes(
    arguments: dict[str, Any],
    client: FigmaClient,
    cache: CacheStore,
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    raw_ids: list[str] = arguments["node_ids"]
    if not raw_ids:
        raise ToolInputError("node_ids must contain at least one ID")

    node_ids = [normalize_node_id(nid) for nid in raw_ids]
    cache_key = f"nodes:{file_key}:{','.join(sorted(node_ids))}"

    raw = await cache.get(cache_key)
    if raw is None:
        raw = await client.get_file_nodes(file_key, node_ids)
        await cache.set(cache_key, raw)

    response = FigmaFileNodes.model_validate(raw)
    nodes_out = {
        nid: data.get("document") for nid, data in response.nodes.items()
    }
    return _text({"file_name": response.name, "nodes": nodes_out})


register(_GET_NODES_TOOL, _handle_get_nodes)


# ---------------------------------------------------------------------------
# Tool: figma_search_nodes
# ---------------------------------------------------------------------------

_SEARCH_NODES_TOOL = types.Tool(
    name="figma_search_nodes",
    description=(
        "Search for nodes within a Figma file by name or type. "
        "Returns matching nodes with their IDs, types, and path within the tree. "
        "At least one of 'name' or 'node_type' must be provided."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "file_key": {
                "type": "string",
                "description": "Figma file key or URL.",
            },
            "name": {
                "type": "string",
                "description": "Case-insensitive substring to match against node names.",
            },
            "node_type": {
                "type": "string",
                "description": (
                    "Filter by node type. Common values: FRAME, COMPONENT, "
                    "COMPONENT_SET, INSTANCE, TEXT, RECTANGLE, GROUP."
                ),
            },
            "page_id": {
                "type": "string",
                "description": "Limit search to a specific page by ID.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return. Default 50, max 200.",
                "default": 50,
                "minimum": 1,
                "maximum": 200,
            },
        },
        "required": ["file_key"],
        "additionalProperties": False,
    },
)


async def _handle_search_nodes(
    arguments: dict[str, Any],
    client: FigmaClient,
    cache: CacheStore,
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    name_filter: str | None = arguments.get("name")
    type_filter: str | None = arguments.get("node_type")
    page_id: str | None = arguments.get("page_id")
    limit: int = min(arguments.get("limit", 50), 200)

    if name_filter is None and type_filter is None:
        raise ToolInputError("Provide at least one of 'name' or 'node_type' to search")

    # Fetch full tree (no depth limit) — cached to avoid redundant large fetches
    raw = await _fetch_file(file_key, client, cache, depth=None)
    document = raw.get("document", {})

    # Narrow to a specific page if requested
    search_roots: list[dict[str, Any]] = []
    for page in document.get("children", []) or []:
        if page_id is None or page.get("id") == page_id:
            search_roots.append(page)

    results: list[dict[str, Any]] = []
    for root in search_roots:
        _search_nodes(
            root,
            name_filter=name_filter,
            type_filter=type_filter,
            path=f"/{document.get('name', 'Document')}",
            results=results,
            limit=limit,
        )
        if len(results) >= limit:
            break

    return _text(
        {
            "file_name": raw.get("name"),
            "total_results": len(results),
            "results": results[:limit],
        }
    )


register(_SEARCH_NODES_TOOL, _handle_search_nodes)
