"""Phase 8 — Webhook Management Tools.

Provides MCP tools for registering, listing, and deleting Figma webhooks
so an LLM agent can set up real-time cache invalidation without leaving
the MCP conversation.
"""

from __future__ import annotations

import json
from typing import Any

from mcp import types

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.exceptions import ToolInputError
from figma_mcpxer.figma.client import FigmaClient
from figma_mcpxer.tools.registry import register


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]


_SUPPORTED_EVENTS = (
    "FILE_UPDATE",
    "FILE_DELETE",
    "FILE_VERSION_UPDATE",
    "LIBRARY_PUBLISH",
    "FILE_COMMENT",
)

# ---------------------------------------------------------------------------
# figma_create_webhook
# ---------------------------------------------------------------------------


async def _handle_create_webhook(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    team_id = arguments["team_id"].strip()
    endpoint = arguments["endpoint"].strip()
    passcode = arguments["passcode"].strip()
    event_type = arguments.get("event_type", "FILE_UPDATE")

    if event_type not in _SUPPORTED_EVENTS:
        raise ToolInputError(
            f"event_type must be one of: {', '.join(_SUPPORTED_EVENTS)}"
        )
    if not endpoint.startswith(("http://", "https://")):
        raise ToolInputError("endpoint must be a valid http:// or https:// URL")

    result = await client.create_webhook(team_id, event_type, endpoint, passcode)
    return _text({
        "created": True,
        "webhook_id": result.get("id"),
        "event_type": result.get("event_type"),
        "endpoint": result.get("endpoint"),
        "status": result.get("status"),
        "note": (
            "Set FIGMA_WEBHOOK_PASSCODE to the same passcode in your server .env "
            "so incoming deliveries are validated."
        ),
    })


register(
    types.Tool(
        name="figma_create_webhook",
        description=(
            "Register a Figma webhook so your server receives real-time FILE_UPDATE "
            "(and other) events. When the server receives an event it automatically "
            "invalidates the file cache so the next tool call fetches fresh data. "
            "Requires a publicly reachable endpoint URL."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "team_id": {
                    "type": "string",
                    "description": "Figma team ID that owns the files to watch.",
                },
                "endpoint": {
                    "type": "string",
                    "description": (
                        "Public HTTPS URL Figma will POST events to. "
                        "Must be https:// in production. "
                        "Route: POST /webhooks/figma on this server."
                    ),
                },
                "passcode": {
                    "type": "string",
                    "description": (
                        "Secret string included in every Figma delivery. "
                        "Set FIGMA_WEBHOOK_PASSCODE to the same value."
                    ),
                },
                "event_type": {
                    "type": "string",
                    "enum": list(_SUPPORTED_EVENTS),
                    "description": "Figma event to subscribe to. Default: FILE_UPDATE.",
                    "default": "FILE_UPDATE",
                },
            },
            "required": ["team_id", "endpoint", "passcode"],
            "additionalProperties": False,
        },
    ),
    _handle_create_webhook,
)

# ---------------------------------------------------------------------------
# figma_list_webhooks
# ---------------------------------------------------------------------------


async def _handle_list_webhooks(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    team_id = arguments["team_id"].strip()
    raw = await client.list_webhooks(team_id)
    webhooks = raw.get("webhooks", [])

    formatted = [
        {
            "id": w.get("id"),
            "event_type": w.get("event_type"),
            "endpoint": w.get("endpoint"),
            "status": w.get("status"),
            "description": w.get("description", ""),
        }
        for w in webhooks
    ]
    return _text({"team_id": team_id, "count": len(formatted), "webhooks": formatted})


register(
    types.Tool(
        name="figma_list_webhooks",
        description="List all webhooks registered for a Figma team.",
        inputSchema={
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "Figma team ID."},
            },
            "required": ["team_id"],
            "additionalProperties": False,
        },
    ),
    _handle_list_webhooks,
)

# ---------------------------------------------------------------------------
# figma_delete_webhook
# ---------------------------------------------------------------------------


async def _handle_delete_webhook(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    webhook_id = arguments["webhook_id"].strip()
    result = await client.delete_webhook(webhook_id)
    return _text({"deleted": True, "webhook_id": webhook_id, "response": result})


register(
    types.Tool(
        name="figma_delete_webhook",
        description="Delete a Figma webhook by its ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "webhook_id": {
                    "type": "string",
                    "description": "Webhook ID returned by figma_create_webhook.",
                },
            },
            "required": ["webhook_id"],
            "additionalProperties": False,
        },
    ),
    _handle_delete_webhook,
)
