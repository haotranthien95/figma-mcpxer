"""Unit tests for Phase 6 — Code Generation Hint tools."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.exceptions import ToolInputError
from figma_mcpxer.tools.codegen import (
    _handle_describe_component,
    _handle_get_css,
    _handle_get_design_tokens_json,
)


def _parse(result: list[Any]) -> Any:
    return json.loads(result[0].text)


@pytest.fixture
def component_set_response() -> dict[str, Any]:
    return {
        "name": "Design",
        "version": "1",
        "nodes": {
            "set:1": {
                "document": {
                    "id": "set:1",
                    "name": "Button",
                    "type": "COMPONENT_SET",
                    "description": "Primary action button",
                    "componentPropertyDefinitions": {
                        "Size": {
                            "type": "VARIANT",
                            "defaultValue": "Medium",
                            "variantOptions": ["Small", "Medium", "Large"],
                        },
                        "Disabled": {
                            "type": "BOOLEAN",
                            "defaultValue": "false",
                        },
                    },
                    "children": [
                        {"id": "c1", "name": "Size=Small, Disabled=false", "type": "COMPONENT", "children": [
                            {"name": "Label", "type": "TEXT"},
                        ]},
                        {"id": "c2", "name": "Size=Medium, Disabled=false", "type": "COMPONENT", "children": []},
                    ],
                }
            }
        },
    }


@pytest.fixture
def frame_node_response() -> dict[str, Any]:
    return {
        "name": "Design",
        "version": "1",
        "nodes": {
            "1:1": {
                "document": {
                    "id": "1:1",
                    "name": "Hero Section",
                    "type": "FRAME",
                    "layoutMode": "VERTICAL",
                    "itemSpacing": 24,
                    "paddingTop": 48,
                    "paddingRight": 0,
                    "paddingBottom": 48,
                    "paddingLeft": 0,
                    "fills": [
                        {"type": "SOLID", "color": {"r": 0.97, "g": 0.97, "b": 0.97, "a": 1.0}, "visible": True}
                    ],
                    "absoluteBoundingBox": {"x": 0, "y": 0, "width": 1440, "height": 600},
                    "cornerRadius": 0,
                    "effects": [],
                    "children": [
                        {"id": "1:2", "name": "Title", "type": "TEXT",
                         "style": {"fontFamily": "Inter", "fontSize": 48, "fontWeight": 700},
                         "fills": [{"type": "SOLID", "color": {"r": 0.1, "g": 0.1, "b": 0.1, "a": 1.0}, "visible": True}]},
                    ],
                }
            }
        },
    }


@pytest.fixture
def file_with_tokens() -> dict[str, Any]:
    return {
        "name": "Design System",
        "version": "1",
        "lastModified": "2024-01-01",
        "schemaVersion": 0,
        "document": {"id": "0:0", "name": "Document", "type": "DOCUMENT", "children": []},
        "components": {},
        "componentSets": {},
        "styles": {
            "fill:1": {"key": "a", "name": "color/primary", "styleType": "FILL", "description": "Brand blue"},
            "text:1": {"key": "b", "name": "type/body", "styleType": "TEXT", "description": ""},
        },
    }


class TestGetCss:
    async def test_returns_css_properties_for_frame(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        frame_node_response: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file_nodes.return_value = frame_node_response
        result = await _handle_get_css(
            {"file_key": "KEY", "node_id": "1:1"}, mock_figma_client, cache_store
        )
        data = _parse(result)
        assert "css_properties" in data
        assert "display" in data["css_properties"]  # vertical auto-layout → flex
        assert "css_block" in data
        assert "width" in data["css_properties"]

    async def test_include_children_adds_children_css(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        frame_node_response: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file_nodes.return_value = frame_node_response
        result = await _handle_get_css(
            {"file_key": "KEY", "node_id": "1:1", "include_children": True},
            mock_figma_client, cache_store,
        )
        data = _parse(result)
        assert "children_css" in data
        assert len(data["children_css"]) == 1  # one child "Title"

    async def test_missing_node_raises_tool_input_error(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        mock_figma_client.get_file_nodes.return_value = {"name": "x", "version": "1", "nodes": {}}
        with pytest.raises(ToolInputError, match="not found"):
            await _handle_get_css(
                {"file_key": "KEY", "node_id": "9:9"}, mock_figma_client, cache_store
            )


class TestDescribeComponent:
    async def test_returns_props_and_variants(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        component_set_response: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file_nodes.return_value = component_set_response
        result = await _handle_describe_component(
            {"file_key": "KEY", "node_id": "set:1"}, mock_figma_client, cache_store
        )
        data = _parse(result)
        assert data["name"] == "Button"
        assert data["type"] == "COMPONENT_SET"
        assert "Size" in data["props"]
        assert data["props"]["Size"]["options"] == ["Small", "Medium", "Large"]
        assert data["variant_count"] == 2
        assert len(data["implementation_hints"]) > 0

    async def test_non_component_node_raises(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        mock_figma_client.get_file_nodes.return_value = {
            "name": "x", "version": "1",
            "nodes": {"1:1": {"document": {"id": "1:1", "name": "Frame", "type": "FRAME"}}},
        }
        with pytest.raises(ToolInputError, match="COMPONENT"):
            await _handle_describe_component(
                {"file_key": "KEY", "node_id": "1:1"}, mock_figma_client, cache_store
            )


class TestGetDesignTokensJson:
    async def test_returns_w3c_token_structure(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        file_with_tokens: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = file_with_tokens
        # fill style node
        mock_figma_client.get_file_nodes.return_value = {
            "name": "x", "version": "1",
            "nodes": {
                "fill:1": {"document": {
                    "fills": [{"type": "SOLID", "color": {"r": 0.0, "g": 0.44, "b": 0.95, "a": 1.0}, "visible": True}]
                }},
                "text:1": {"document": {
                    "style": {"fontFamily": "Inter", "fontSize": 16, "fontWeight": 400}
                }},
            },
        }
        from figma_mcpxer.exceptions import FigmaAuthError
        mock_figma_client.get_local_variables.side_effect = FigmaAuthError()

        result = await _handle_get_design_tokens_json(
            {"file_key": "KEY", "include_variables": True}, mock_figma_client, cache_store
        )
        data = _parse(result)
        assert "$schema" in data
        assert "color" in data
        assert "typography" in data
