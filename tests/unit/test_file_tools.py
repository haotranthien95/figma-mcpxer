"""Unit tests for Phase 2 file & node tools.

The Figma client is mocked so these tests run without network access.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.exceptions import ToolInputError
from figma_mcpxer.tools.file import (
    _handle_get_file,
    _handle_get_node,
    _handle_get_nodes,
    _handle_list_pages,
    _handle_search_nodes,
)


def _parse_result(result: list[Any]) -> Any:
    return json.loads(result[0].text)


class TestGetFile:
    async def test_returns_name_and_pages(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_figma_file: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = sample_figma_file
        result = await _handle_get_file(
            {"file_key": "KEY123"}, mock_figma_client, cache_store
        )
        data = _parse_result(result)
        assert data["name"] == "Test Design"
        assert data["version"] == "99999"
        assert "tree" in data

    async def test_uses_default_depth_2(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_figma_file: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = sample_figma_file
        await _handle_get_file({"file_key": "KEY"}, mock_figma_client, cache_store)
        mock_figma_client.get_file.assert_called_once_with("KEY", depth=2)

    async def test_accepts_figma_url_as_file_key(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_figma_file: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = sample_figma_file
        url = "https://www.figma.com/design/AbCd1234/My-File"
        await _handle_get_file({"file_key": url}, mock_figma_client, cache_store)
        mock_figma_client.get_file.assert_called_once_with("AbCd1234", depth=2)

    async def test_caches_response_on_second_call(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_figma_file: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = sample_figma_file
        await _handle_get_file({"file_key": "KEY"}, mock_figma_client, cache_store)
        await _handle_get_file({"file_key": "KEY"}, mock_figma_client, cache_store)
        # Second call should hit cache, not the client
        assert mock_figma_client.get_file.call_count == 1


class TestListPages:
    async def test_returns_all_pages_with_child_counts(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_figma_file: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = sample_figma_file
        result = await _handle_list_pages({"file_key": "KEY"}, mock_figma_client, cache_store)
        data = _parse_result(result)
        assert len(data["pages"]) == 2
        assert data["pages"][0]["name"] == "Page 1"
        assert data["pages"][0]["child_count"] == 1

    async def test_fetches_with_depth_1(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_figma_file: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = sample_figma_file
        await _handle_list_pages({"file_key": "KEY"}, mock_figma_client, cache_store)
        mock_figma_client.get_file.assert_called_once_with("KEY", depth=1)


class TestGetNode:
    async def test_returns_node_data(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_figma_nodes_response: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file_nodes.return_value = sample_figma_nodes_response
        result = await _handle_get_node(
            {"file_key": "KEY", "node_id": "1:1"}, mock_figma_client, cache_store
        )
        data = _parse_result(result)
        assert data["node"]["id"] == "1:1"
        assert data["node"]["name"] == "Hero Frame"

    async def test_normalizes_dash_node_id(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_figma_nodes_response: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file_nodes.return_value = sample_figma_nodes_response
        await _handle_get_node(
            {"file_key": "KEY", "node_id": "1-1"}, mock_figma_client, cache_store
        )
        mock_figma_client.get_file_nodes.assert_called_once_with("KEY", ["1:1"])

    async def test_missing_node_raises_tool_input_error(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        mock_figma_client.get_file_nodes.return_value = {
            "name": "X", "version": "1", "nodes": {}
        }
        with pytest.raises(ToolInputError, match="not found"):
            await _handle_get_node(
                {"file_key": "KEY", "node_id": "9:9"}, mock_figma_client, cache_store
            )


class TestGetNodes:
    async def test_returns_map_of_nodes(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_figma_nodes_response: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file_nodes.return_value = sample_figma_nodes_response
        result = await _handle_get_nodes(
            {"file_key": "KEY", "node_ids": ["1:1"]}, mock_figma_client, cache_store
        )
        data = _parse_result(result)
        assert "1:1" in data["nodes"]

    async def test_empty_node_ids_raises_tool_input_error(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        with pytest.raises(ToolInputError):
            await _handle_get_nodes(
                {"file_key": "KEY", "node_ids": []}, mock_figma_client, cache_store
            )


class TestSearchNodes:
    async def test_search_by_name_finds_matching_nodes(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_figma_file: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = sample_figma_file
        result = await _handle_search_nodes(
            {"file_key": "KEY", "name": "Button"}, mock_figma_client, cache_store
        )
        data = _parse_result(result)
        assert data["total_results"] >= 1
        names = [r["name"] for r in data["results"]]
        assert any("Button" in n for n in names)

    async def test_search_by_type_returns_only_matching_type(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_figma_file: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = sample_figma_file
        result = await _handle_search_nodes(
            {"file_key": "KEY", "node_type": "TEXT"}, mock_figma_client, cache_store
        )
        data = _parse_result(result)
        for node in data["results"]:
            assert node["type"] == "TEXT"

    async def test_no_filters_raises_tool_input_error(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        with pytest.raises(ToolInputError, match="at least one"):
            await _handle_search_nodes(
                {"file_key": "KEY"}, mock_figma_client, cache_store
            )

    async def test_limit_caps_results(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        sample_figma_file: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = sample_figma_file
        result = await _handle_search_nodes(
            {"file_key": "KEY", "node_type": "FRAME", "limit": 1},
            mock_figma_client,
            cache_store,
        )
        data = _parse_result(result)
        assert len(data["results"]) <= 1
