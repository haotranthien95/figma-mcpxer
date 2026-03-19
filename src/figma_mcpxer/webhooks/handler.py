"""Phase 8 — Figma Webhook Event Handler.

Figma sends an HTTP POST to the endpoint registered with create_webhook.
This module validates the delivery, parses the event, and invalidates the
relevant cache entries so the next MCP tool call fetches fresh data.

Webhook payload shape (Figma v2):
  {
    "event_type": "FILE_UPDATE" | "FILE_DELETE" | ...,
    "passcode":   "your-secret",
    "timestamp":  "2024-01-01T00:00:00Z",
    "webhook_id": "123",
    "file_key":   "abc...",
    "file_name":  "My Design"
  }
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from figma_mcpxer.cache.store import CacheStore

logger = logging.getLogger(__name__)


class WebhookEvent(BaseModel):
    """Pydantic model for an incoming Figma webhook payload."""

    event_type: str
    passcode: str
    timestamp: str
    webhook_id: str
    file_key: str = Field(default="")
    file_name: str = Field(default="")


def verify_passcode(received: str, expected: str | None) -> bool:
    """Return True if the passcode matches the configured secret.

    When no passcode is configured we accept all deliveries (dev mode).
    """
    if expected is None:
        return True
    return received == expected


async def handle_webhook_event(event: WebhookEvent, cache: CacheStore) -> dict[str, Any]:
    """Process an inbound Figma webhook event.

    Currently handles FILE_UPDATE by invalidating all cached data for that
    file so subsequent MCP tool calls fetch fresh content from the Figma API.

    Returns a summary dict logged and returned in the HTTP response body.
    """
    summary: dict[str, Any] = {
        "event_type": event.event_type,
        "webhook_id": event.webhook_id,
        "file_key": event.file_key,
        "file_name": event.file_name,
        "action": "ignored",
    }

    if event.event_type in ("FILE_UPDATE", "FILE_DELETE", "LIBRARY_PUBLISH"):
        await _invalidate_file_cache(event.file_key, cache)
        summary["action"] = "cache_invalidated"
        logger.info(
            "Webhook %s: invalidated cache for file %s (%s)",
            event.event_type,
            event.file_key,
            event.file_name,
        )
    else:
        logger.debug("Webhook %s received — no cache action needed", event.event_type)

    return summary


async def _invalidate_file_cache(file_key: str, cache: CacheStore) -> None:
    """Delete all known cache keys for a given file_key.

    We cannot enumerate keys in the in-memory store, so we delete the
    known key patterns used by shared.py. Redis users benefit from
    pattern-based deletion in RedisCacheStore.clear_pattern() (future).
    """
    # File fetch keys (various depths)
    for depth in (None, 1, 2, 3, 4):
        await cache.delete(f"file:{file_key}:depth:{depth}")

    # Style-related caches reuse the file cache key, so covered above.
    # Variables cache
    await cache.delete(f"variables:{file_key}")
    # Image fills cache
    await cache.delete(f"image_fills:{file_key}")
    logger.debug("Cache cleared for file %s", file_key)
