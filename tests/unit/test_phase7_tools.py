"""Unit tests for Phase 7 — Collaboration & Metadata Tools."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.tools.collaboration import (
    _handle_get_comments,
    _handle_get_projects,
    _handle_get_team_components,
    _handle_get_versions,
    _handle_post_comment,
)


@pytest.fixture
def sample_comments_response() -> dict[str, Any]:
    return {
        "comments": [
            {
                "id": "c1",
                "message": "Update the padding here",
                "user": {"handle": "alice"},
                "created_at": "2024-01-15T10:00:00Z",
                "resolved_at": None,
                "client_meta": {"node_id": "1:1"},
                "parent_id": None,
            },
            {
                "id": "c2",
                "message": "General file comment",
                "user": {"handle": "bob"},
                "created_at": "2024-01-16T09:00:00Z",
                "resolved_at": None,
                "client_meta": None,
                "parent_id": None,
            },
        ]
    }


@pytest.fixture
def sample_versions_response() -> dict[str, Any]:
    return {
        "versions": [
            {
                "id": "v3",
                "label": "Final handoff",
                "description": "Ready for dev",
                "created_at": "2024-01-20T12:00:00Z",
                "user": {"handle": "designer"},
            },
            {
                "id": "v2",
                "label": None,
                "description": "",
                "created_at": "2024-01-18T08:00:00Z",
                "user": {"handle": "designer"},
            },
        ]
    }


class TestGetComments:
    async def test_get_comments_returns_all_when_no_node_filter(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_comments_response: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file_comments.return_value = sample_comments_response

        result = await _handle_get_comments(
            {"file_key": "abc123"}, mock_figma_client, cache_store
        )

        data = json.loads(result[0].text)
        assert data["count"] == 2
        assert data["node_filter"] is None

    async def test_get_comments_filters_by_node_id(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_comments_response: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file_comments.return_value = sample_comments_response

        result = await _handle_get_comments(
            {"file_key": "abc123", "node_id": "1:1"}, mock_figma_client, cache_store
        )

        data = json.loads(result[0].text)
        assert data["count"] == 1
        assert data["comments"][0]["id"] == "c1"

    async def test_get_comments_normalises_node_id_format(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_comments_response: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file_comments.return_value = sample_comments_response

        # Figma URLs use hyphen, API uses colon — both should match
        result = await _handle_get_comments(
            {"file_key": "abc123", "node_id": "1-1"}, mock_figma_client, cache_store
        )

        data = json.loads(result[0].text)
        assert data["count"] == 1


class TestPostComment:
    async def test_post_comment_returns_posted_true(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        mock_figma_client.post_file_comment.return_value = {
            "id": "c99",
            "message": "Looks good!",
            "user": {"handle": "bot"},
            "created_at": "2024-01-21T00:00:00Z",
            "resolved_at": None,
            "client_meta": None,
            "parent_id": None,
        }

        result = await _handle_post_comment(
            {"file_key": "abc123", "message": "Looks good!"},
            mock_figma_client,
            cache_store,
        )

        data = json.loads(result[0].text)
        assert data["posted"] is True
        assert data["comment"]["id"] == "c99"

    async def test_post_comment_empty_message_raises(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        from figma_mcpxer.exceptions import ToolInputError

        with pytest.raises(ToolInputError, match="empty"):
            await _handle_post_comment(
                {"file_key": "abc123", "message": "   "},
                mock_figma_client,
                cache_store,
            )


class TestGetVersions:
    async def test_get_versions_returns_formatted_list(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_versions_response: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file_versions.return_value = sample_versions_response

        result = await _handle_get_versions(
            {"file_key": "abc123"}, mock_figma_client, cache_store
        )

        data = json.loads(result[0].text)
        assert data["count"] == 2
        assert data["versions"][0]["label"] == "Final handoff"
        assert data["versions"][0]["author"] == "designer"

    async def test_get_versions_respects_limit(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_versions_response: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file_versions.return_value = sample_versions_response

        result = await _handle_get_versions(
            {"file_key": "abc123", "limit": 1}, mock_figma_client, cache_store
        )

        data = json.loads(result[0].text)
        assert data["count"] == 1


class TestGetTeamComponents:
    async def test_get_team_components_returns_formatted_list(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        mock_figma_client.get_team_components.return_value = {
            "meta": {
                "components": [
                    {
                        "key": "btn-key",
                        "name": "Button/Primary",
                        "description": "Main CTA button",
                        "file_key": "file1",
                        "node_id": "1:10",
                        "thumbnail_url": "https://cdn.figma.com/thumb",
                        "containing_frame": {"name": "Buttons"},
                    }
                ]
            }
        }

        result = await _handle_get_team_components(
            {"team_id": "team123"}, mock_figma_client, cache_store
        )

        data = json.loads(result[0].text)
        assert data["count"] == 1
        assert data["components"][0]["name"] == "Button/Primary"
        assert data["components"][0]["containing_frame"] == "Buttons"


class TestGetProjects:
    async def test_get_projects_returns_formatted_list(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        mock_figma_client.get_team_projects.return_value = {
            "projects": [
                {"id": "proj1", "name": "Design System"},
                {"id": "proj2", "name": "Marketing Site"},
            ]
        }

        result = await _handle_get_projects(
            {"team_id": "team123"}, mock_figma_client, cache_store
        )

        data = json.loads(result[0].text)
        assert data["count"] == 2
        assert data["projects"][0]["name"] == "Design System"
