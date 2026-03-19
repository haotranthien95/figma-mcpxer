"""Phase 7 — Collaboration & Metadata Tools.

Provides MCP tools for reading and posting comments, browsing version
history, and discovering team libraries and projects.
"""

from __future__ import annotations

import json
from typing import Any

from mcp import types

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.exceptions import ToolInputError
from figma_mcpxer.figma.client import FigmaClient
from figma_mcpxer.tools.registry import register
from figma_mcpxer.utils.url import extract_file_key, normalize_node_id


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]


# ---------------------------------------------------------------------------
# figma_get_comments
# ---------------------------------------------------------------------------


def _format_comment(c: dict[str, Any]) -> dict[str, Any]:
    """Extract the fields most useful to an LLM from a raw comment object."""
    return {
        "id": c.get("id"),
        "message": c.get("message"),
        "author": c.get("user", {}).get("handle"),
        "created_at": c.get("created_at"),
        "resolved_at": c.get("resolved_at"),
        "node_id": (c.get("client_meta") or {}).get("node_id"),
        "parent_id": c.get("parent_id"),
    }


async def _handle_get_comments(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    node_id = arguments.get("node_id")
    if node_id:
        node_id = normalize_node_id(node_id)

    raw = await client.get_file_comments(file_key)
    comments = raw.get("comments", [])

    if node_id:
        comments = [
            c for c in comments
            if (c.get("client_meta") or {}).get("node_id") == node_id
        ]

    return _text({
        "file_key": file_key,
        "node_filter": node_id,
        "count": len(comments),
        "comments": [_format_comment(c) for c in comments],
    })


register(
    types.Tool(
        name="figma_get_comments",
        description=(
            "Fetch all comments on a Figma file. Optionally filter by node_id "
            "to get only comments pinned to a specific element. "
            "Useful for reading designer annotations and review feedback."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
                "node_id": {
                    "type": "string",
                    "description": "Filter to comments pinned to this node (optional).",
                },
            },
            "required": ["file_key"],
            "additionalProperties": False,
        },
    ),
    _handle_get_comments,
)

# ---------------------------------------------------------------------------
# figma_post_comment
# ---------------------------------------------------------------------------


async def _handle_post_comment(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    message = arguments["message"].strip()
    if not message:
        raise ToolInputError("message must not be empty")

    node_id = arguments.get("node_id")
    if node_id:
        node_id = normalize_node_id(node_id)

    result = await client.post_file_comment(file_key, message, node_id=node_id)
    return _text({
        "file_key": file_key,
        "posted": True,
        "comment": _format_comment(result),
    })


register(
    types.Tool(
        name="figma_post_comment",
        description=(
            "Post a comment on a Figma file. Optionally pin it to a specific node. "
            "Useful for leaving implementation notes or flagging design questions."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
                "message": {"type": "string", "description": "Comment text to post."},
                "node_id": {
                    "type": "string",
                    "description": "Pin the comment to this node ID (optional).",
                },
            },
            "required": ["file_key", "message"],
            "additionalProperties": False,
        },
    ),
    _handle_post_comment,
)

# ---------------------------------------------------------------------------
# figma_get_versions
# ---------------------------------------------------------------------------


async def _handle_get_versions(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    limit = int(arguments.get("limit", 20))

    raw = await client.get_file_versions(file_key)
    versions = raw.get("versions", [])[:limit]

    formatted = [
        {
            "id": v.get("id"),
            "label": v.get("label"),
            "description": v.get("description", ""),
            "created_at": v.get("created_at"),
            "author": v.get("user", {}).get("handle"),
        }
        for v in versions
    ]
    return _text({
        "file_key": file_key,
        "count": len(formatted),
        "versions": formatted,
    })


register(
    types.Tool(
        name="figma_get_versions",
        description=(
            "List the version history of a Figma file (most recent first). "
            "Shows version labels, descriptions, author, and timestamps."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
                "limit": {
                    "type": "integer",
                    "description": "Maximum versions to return. Default 20.",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": ["file_key"],
            "additionalProperties": False,
        },
    ),
    _handle_get_versions,
)

# ---------------------------------------------------------------------------
# figma_get_team_components
# ---------------------------------------------------------------------------


async def _handle_get_team_components(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    team_id = arguments["team_id"].strip()
    raw = await client.get_team_components(team_id)
    components = raw.get("meta", {}).get("components", [])

    formatted = [
        {
            "key": c.get("key"),
            "name": c.get("name"),
            "description": c.get("description", ""),
            "file_key": c.get("file_key"),
            "node_id": c.get("node_id"),
            "thumbnail_url": c.get("thumbnail_url"),
            "containing_frame": c.get("containing_frame", {}).get("name"),
        }
        for c in components
    ]
    return _text({"team_id": team_id, "count": len(formatted), "components": formatted})


register(
    types.Tool(
        name="figma_get_team_components",
        description=(
            "List all components published from a Figma team library. "
            "Returns component key, name, description, and the file/node where it lives. "
            "Use the key to reference the component in code generation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "team_id": {
                    "type": "string",
                    "description": "Figma team ID (visible in the team's Figma URL).",
                },
            },
            "required": ["team_id"],
            "additionalProperties": False,
        },
    ),
    _handle_get_team_components,
)

# ---------------------------------------------------------------------------
# figma_get_projects
# ---------------------------------------------------------------------------


async def _handle_get_projects(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    team_id = arguments["team_id"].strip()
    raw = await client.get_team_projects(team_id)
    projects = raw.get("projects", [])

    formatted = [
        {"id": p.get("id"), "name": p.get("name")}
        for p in projects
    ]
    return _text({"team_id": team_id, "count": len(formatted), "projects": formatted})


register(
    types.Tool(
        name="figma_get_projects",
        description=(
            "List all projects for a Figma team. "
            "Returns project IDs and names — use the project ID to find files."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "team_id": {
                    "type": "string",
                    "description": "Figma team ID (visible in the team's Figma URL).",
                },
            },
            "required": ["team_id"],
            "additionalProperties": False,
        },
    ),
    _handle_get_projects,
)
