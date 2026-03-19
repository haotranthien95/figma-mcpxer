"""Unit tests for Phase 8 — Webhook Handler & Management Tools."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.tools.webhooks import (
    _handle_create_webhook,
    _handle_delete_webhook,
    _handle_list_webhooks,
)
from figma_mcpxer.webhooks.handler import (
    WebhookEvent,
    _invalidate_file_cache,
    handle_webhook_event,
    verify_passcode,
)


# ---------------------------------------------------------------------------
# verify_passcode
# ---------------------------------------------------------------------------


class TestVerifyPasscode:
    def test_no_configured_passcode_accepts_any(self) -> None:
        assert verify_passcode("anything", None) is True

    def test_matching_passcode_returns_true(self) -> None:
        assert verify_passcode("secret", "secret") is True

    def test_wrong_passcode_returns_false(self) -> None:
        assert verify_passcode("wrong", "secret") is False


# ---------------------------------------------------------------------------
# handle_webhook_event
# ---------------------------------------------------------------------------


@pytest.fixture
def file_update_event() -> WebhookEvent:
    return WebhookEvent(
        event_type="FILE_UPDATE",
        passcode="test-secret",
        timestamp="2024-01-01T00:00:00Z",
        webhook_id="wh1",
        file_key="abc123",
        file_name="My Design",
    )


class TestHandleWebhookEvent:
    async def test_file_update_invalidates_cache(
        self,
        cache_store: CacheStore,
        file_update_event: WebhookEvent,
    ) -> None:
        # Pre-populate cache
        await cache_store.set("file:abc123:depth:None", {"data": "stale"})
        await cache_store.set("variables:abc123", {"vars": "stale"})

        summary = await handle_webhook_event(file_update_event, cache_store)

        assert summary["action"] == "cache_invalidated"
        # Cache should be cleared
        assert await cache_store.get("file:abc123:depth:None") is None
        assert await cache_store.get("variables:abc123") is None

    async def test_file_delete_invalidates_cache(
        self,
        cache_store: CacheStore,
    ) -> None:
        event = WebhookEvent(
            event_type="FILE_DELETE",
            passcode="x",
            timestamp="2024-01-01T00:00:00Z",
            webhook_id="wh2",
            file_key="del123",
            file_name="Deleted",
        )
        await cache_store.set("file:del123:depth:None", {"data": "old"})

        summary = await handle_webhook_event(event, cache_store)

        assert summary["action"] == "cache_invalidated"
        assert await cache_store.get("file:del123:depth:None") is None

    async def test_unknown_event_type_is_ignored(
        self,
        cache_store: CacheStore,
    ) -> None:
        event = WebhookEvent(
            event_type="PING",
            passcode="x",
            timestamp="2024-01-01T00:00:00Z",
            webhook_id="wh3",
        )

        summary = await handle_webhook_event(event, cache_store)

        assert summary["action"] == "ignored"

    async def test_invalidate_clears_all_known_key_patterns(
        self,
        cache_store: CacheStore,
    ) -> None:
        fk = "fk999"
        keys = [
            f"file:{fk}:depth:None",
            f"file:{fk}:depth:1",
            f"variables:{fk}",
            f"image_fills:{fk}",
        ]
        for k in keys:
            await cache_store.set(k, "data")

        await _invalidate_file_cache(fk, cache_store)

        for k in keys:
            assert await cache_store.get(k) is None


# ---------------------------------------------------------------------------
# Webhook management MCP tools
# ---------------------------------------------------------------------------


class TestCreateWebhook:
    async def test_create_webhook_returns_webhook_id(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        mock_figma_client.create_webhook.return_value = {
            "id": "wh100",
            "event_type": "FILE_UPDATE",
            "endpoint": "https://myserver.com/webhooks/figma",
            "status": "ACTIVE",
        }

        result = await _handle_create_webhook(
            {
                "team_id": "team1",
                "endpoint": "https://myserver.com/webhooks/figma",
                "passcode": "my-secret",
            },
            mock_figma_client,
            cache_store,
        )

        data = json.loads(result[0].text)
        assert data["created"] is True
        assert data["webhook_id"] == "wh100"

    async def test_create_webhook_invalid_event_type_raises(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        from figma_mcpxer.exceptions import ToolInputError

        with pytest.raises(ToolInputError, match="event_type"):
            await _handle_create_webhook(
                {
                    "team_id": "team1",
                    "endpoint": "https://example.com/hook",
                    "passcode": "x",
                    "event_type": "INVALID_TYPE",
                },
                mock_figma_client,
                cache_store,
            )

    async def test_create_webhook_invalid_endpoint_raises(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        from figma_mcpxer.exceptions import ToolInputError

        with pytest.raises(ToolInputError, match="endpoint"):
            await _handle_create_webhook(
                {
                    "team_id": "team1",
                    "endpoint": "not-a-url",
                    "passcode": "x",
                },
                mock_figma_client,
                cache_store,
            )


class TestListWebhooks:
    async def test_list_webhooks_returns_formatted_list(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        mock_figma_client.list_webhooks.return_value = {
            "webhooks": [
                {
                    "id": "wh1",
                    "event_type": "FILE_UPDATE",
                    "endpoint": "https://example.com/hook",
                    "status": "ACTIVE",
                    "description": "",
                }
            ]
        }

        result = await _handle_list_webhooks(
            {"team_id": "team1"}, mock_figma_client, cache_store
        )

        data = json.loads(result[0].text)
        assert data["count"] == 1
        assert data["webhooks"][0]["status"] == "ACTIVE"


class TestDeleteWebhook:
    async def test_delete_webhook_returns_deleted_true(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        mock_figma_client.delete_webhook.return_value = {"id": "wh1"}

        result = await _handle_delete_webhook(
            {"webhook_id": "wh1"}, mock_figma_client, cache_store
        )

        data = json.loads(result[0].text)
        assert data["deleted"] is True
        assert data["webhook_id"] == "wh1"
