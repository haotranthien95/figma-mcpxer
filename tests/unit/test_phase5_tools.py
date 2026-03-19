"""Unit tests for Phase 5 — Layout & Structure tools."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.exceptions import ToolInputError
from figma_mcpxer.tools.layout import (
    _handle_get_absolute_bounds,
    _handle_get_auto_layout,
    _handle_get_constraints,
    _handle_get_fills,
)


def _parse(result: list[Any]) -> Any:
    return json.loads(result[0].text)


@pytest.fixture
def frame_nodes_response() -> dict[str, Any]:
    return {
        "name": "Design",
        "version": "1",
        "nodes": {
            "1:1": {
                "document": {
                    "id": "1:1",
                    "name": "Card",
                    "type": "FRAME",
                    "layoutMode": "VERTICAL",
                    "itemSpacing": 16,
                    "paddingTop": 24,
                    "paddingRight": 24,
                    "paddingBottom": 24,
                    "paddingLeft": 24,
                    "primaryAxisAlignItems": "MIN",
                    "counterAxisAlignItems": "MIN",
                    "absoluteBoundingBox": {"x": 0, "y": 0, "width": 320, "height": 400},
                    "constraints": {"horizontal": "LEFT", "vertical": "TOP"},
                    "fills": [
                        {"type": "SOLID", "color": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0}, "visible": True}
                    ],
                    "children": [],
                }
            }
        },
    }


class TestGetAutoLayout:
    async def test_returns_flex_css_for_vertical_frame(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        frame_nodes_response: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file_nodes.return_value = frame_nodes_response
        result = await _handle_get_auto_layout(
            {"file_key": "KEY", "node_ids": ["1:1"]}, mock_figma_client, cache_store
        )
        data = _parse(result)
        node = data["nodes"][0]
        assert node["is_auto_layout"] is True
        assert node["direction"] == "column"
        assert node["css"]["display"] == "flex"
        assert node["css"]["gap"] == "16px"

    async def test_empty_node_ids_raises(
        self, mock_figma_client: AsyncMock, cache_store: CacheStore
    ) -> None:
        with pytest.raises(ToolInputError):
            await _handle_get_auto_layout(
                {"file_key": "KEY", "node_ids": []}, mock_figma_client, cache_store
            )


class TestGetConstraints:
    async def test_returns_constraints_and_hint(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        frame_nodes_response: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file_nodes.return_value = frame_nodes_response
        result = await _handle_get_constraints(
            {"file_key": "KEY", "node_ids": ["1:1"]}, mock_figma_client, cache_store
        )
        data = _parse(result)
        node = data["nodes"][0]
        assert node["constraints"]["horizontal"] == "LEFT"
        assert "hint" in node


class TestGetAbsoluteBounds:
    async def test_returns_bounds_with_css(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        frame_nodes_response: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file_nodes.return_value = frame_nodes_response
        result = await _handle_get_absolute_bounds(
            {"file_key": "KEY", "node_ids": ["1:1"]}, mock_figma_client, cache_store
        )
        data = _parse(result)
        node = data["nodes"][0]
        assert node["bounding_box"]["width"] == 320
        assert node["css"]["width"] == "320px"
        assert node["css"]["height"] == "400px"


class TestGetFills:
    async def test_returns_solid_fill_with_css(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        frame_nodes_response: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file_nodes.return_value = frame_nodes_response
        result = await _handle_get_fills(
            {"file_key": "KEY", "node_ids": ["1:1"]}, mock_figma_client, cache_store
        )
        data = _parse(result)
        node = data["nodes"][0]
        assert node["fill_count"] == 1
        assert node["fills"][0]["type"] == "SOLID"
        assert node["fills"][0]["css"] is not None
