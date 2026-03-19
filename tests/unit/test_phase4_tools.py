"""Unit tests for Phase 4 — Component & Asset tools."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.exceptions import ToolInputError
from figma_mcpxer.tools.components import (
    _handle_export_image,
    _handle_export_images,
    _handle_get_component_sets,
    _handle_get_components,
    _handle_get_images,
    _handle_get_styles,
)


def _parse(result: list[Any]) -> Any:
    return json.loads(result[0].text)


@pytest.fixture
def file_with_components() -> dict[str, Any]:
    return {
        "name": "Design System",
        "version": "1",
        "lastModified": "2024-01-01",
        "schemaVersion": 0,
        "document": {
            "id": "0:0", "name": "Document", "type": "DOCUMENT",
            "children": [],
        },
        "components": {
            "comp:1": {"key": "abc", "name": "Button", "description": "Primary button"},
            "comp:2": {"key": "def", "name": "Input", "description": "Text input"},
        },
        "componentSets": {
            "set:1": {"key": "ghi", "name": "Button", "description": "Button variants"},
        },
        "styles": {
            "fill:1": {"key": "x", "name": "color/bg", "styleType": "FILL", "description": ""},
            "text:1": {"key": "y", "name": "type/body", "styleType": "TEXT", "description": ""},
        },
    }


class TestGetComponents:
    async def test_returns_component_list(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        file_with_components: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = file_with_components
        result = await _handle_get_components({"file_key": "KEY"}, mock_figma_client, cache_store)
        data = _parse(result)
        assert data["count"] == 2
        names = {c["name"] for c in data["components"]}
        assert "Button" in names
        assert "Input" in names

    async def test_include_details_fetches_nodes(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        file_with_components: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = file_with_components
        mock_figma_client.get_file_nodes.return_value = {
            "name": "x", "version": "1",
            "nodes": {
                "comp:1": {"document": {"id": "comp:1", "name": "Button", "type": "COMPONENT", "children": []}},
                "comp:2": {"document": {"id": "comp:2", "name": "Input", "type": "COMPONENT", "children": []}},
            },
        }
        result = await _handle_get_components(
            {"file_key": "KEY", "include_details": True}, mock_figma_client, cache_store
        )
        data = _parse(result)
        assert data["count"] == 2
        mock_figma_client.get_file_nodes.assert_called_once()


class TestGetComponentSets:
    async def test_returns_variant_properties(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        file_with_components: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = file_with_components
        mock_figma_client.get_file_nodes.return_value = {
            "name": "x", "version": "1",
            "nodes": {
                "set:1": {
                    "document": {
                        "id": "set:1", "name": "Button", "type": "COMPONENT_SET",
                        "componentPropertyDefinitions": {
                            "Size": {
                                "type": "VARIANT",
                                "defaultValue": "Medium",
                                "variantOptions": ["Small", "Medium", "Large"],
                            }
                        },
                        "children": [
                            {"name": "Size=Small", "type": "COMPONENT"},
                            {"name": "Size=Medium", "type": "COMPONENT"},
                            {"name": "Size=Large", "type": "COMPONENT"},
                        ],
                    }
                }
            },
        }
        result = await _handle_get_component_sets({"file_key": "KEY"}, mock_figma_client, cache_store)
        data = _parse(result)
        assert data["count"] == 1
        button_set = data["component_sets"][0]
        assert "Size" in button_set["property_definitions"]
        assert button_set["variant_count"] == 3


class TestGetStyles:
    async def test_groups_styles_by_type(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        file_with_components: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = file_with_components
        result = await _handle_get_styles({"file_key": "KEY"}, mock_figma_client, cache_store)
        data = _parse(result)
        assert data["total"] == 2
        assert "FILL" in data["by_type"]
        assert "TEXT" in data["by_type"]


class TestExportImage:
    async def test_returns_url_for_node(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        mock_figma_client.export_images.return_value = {
            "err": None,
            "images": {"1:1": "https://cdn.figma.com/image/abc.png"},
        }
        result = await _handle_export_image(
            {"file_key": "KEY", "node_id": "1:1", "format": "png"},
            mock_figma_client, cache_store,
        )
        data = _parse(result)
        assert "cdn.figma.com" in data["url"]

    async def test_invalid_format_raises_tool_input_error(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        with pytest.raises(ToolInputError, match="format"):
            await _handle_export_image(
                {"file_key": "KEY", "node_id": "1:1", "format": "gif"},
                mock_figma_client, cache_store,
            )

    async def test_invalid_scale_raises_tool_input_error(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        with pytest.raises(ToolInputError, match="scale"):
            await _handle_export_image(
                {"file_key": "KEY", "node_id": "1:1", "scale": 10.0},
                mock_figma_client, cache_store,
            )


class TestGetImages:
    async def test_returns_image_fill_map(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        mock_figma_client.get_file_image_fills.return_value = {
            "err": None,
            "meta": {"images": {"ref:abc": "https://cdn.figma.com/img/abc.png"}},
        }
        result = await _handle_get_images({"file_key": "KEY"}, mock_figma_client, cache_store)
        data = _parse(result)
        assert data["count"] == 1
        assert "ref:abc" in data["images"]
