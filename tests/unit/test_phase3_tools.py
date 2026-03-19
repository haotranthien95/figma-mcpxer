"""Unit tests for Phase 3 — Design Token tools."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.tools.tokens import (
    _handle_get_colors,
    _handle_get_effects,
    _handle_get_spacing,
    _handle_get_typography,
    _handle_get_variables,
)


def _parse(result: list[Any]) -> Any:
    return json.loads(result[0].text)


@pytest.fixture
def file_with_styles() -> dict[str, Any]:
    """A minimal Figma file response with one of each style type."""
    return {
        "name": "Design System",
        "version": "1",
        "lastModified": "2024-01-01",
        "schemaVersion": 0,
        "document": {
            "id": "0:0",
            "name": "Document",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "0:1",
                    "name": "Page 1",
                    "type": "CANVAS",
                    "children": [
                        {
                            "id": "frame:1",
                            "name": "Card",
                            "type": "FRAME",
                            "layoutMode": "VERTICAL",
                            "itemSpacing": 16,
                            "paddingTop": 24,
                            "paddingRight": 24,
                            "paddingBottom": 24,
                            "paddingLeft": 24,
                            "children": [],
                        }
                    ],
                }
            ],
        },
        "styles": {
            "fill:1": {"key": "abc", "name": "color/primary", "styleType": "FILL", "description": "Brand blue"},
            "text:1": {"key": "def", "name": "heading/h1", "styleType": "TEXT", "description": ""},
            "effect:1": {"key": "ghi", "name": "shadow/md", "styleType": "EFFECT", "description": ""},
        },
        "components": {},
        "componentSets": {},
    }


@pytest.fixture
def fill_style_node() -> dict[str, Any]:
    return {
        "name": "nodes response",
        "version": "1",
        "nodes": {
            "fill:1": {
                "document": {
                    "id": "fill:1",
                    "name": "color/primary",
                    "type": "RECTANGLE",
                    "fills": [{"type": "SOLID", "color": {"r": 0.0, "g": 0.44, "b": 0.95, "a": 1.0}, "visible": True}],
                }
            }
        },
    }


@pytest.fixture
def text_style_node() -> dict[str, Any]:
    return {
        "name": "nodes response",
        "version": "1",
        "nodes": {
            "text:1": {
                "document": {
                    "id": "text:1",
                    "name": "heading/h1",
                    "type": "TEXT",
                    "style": {
                        "fontFamily": "Inter",
                        "fontSize": 32,
                        "fontWeight": 700,
                        "lineHeightUnit": "PIXELS",
                        "lineHeightPx": 40,
                    },
                }
            }
        },
    }


@pytest.fixture
def effect_style_node() -> dict[str, Any]:
    return {
        "name": "nodes response",
        "version": "1",
        "nodes": {
            "effect:1": {
                "document": {
                    "id": "effect:1",
                    "name": "shadow/md",
                    "type": "RECTANGLE",
                    "effects": [{
                        "type": "DROP_SHADOW",
                        "visible": True,
                        "offset": {"x": 0, "y": 4},
                        "radius": 8,
                        "spread": 0,
                        "color": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 0.12},
                    }],
                }
            }
        },
    }


class TestGetColors:
    async def test_returns_color_list_with_hex(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        file_with_styles: dict[str, Any],
        fill_style_node: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = file_with_styles
        mock_figma_client.get_file_nodes.return_value = fill_style_node

        result = await _handle_get_colors({"file_key": "KEY"}, mock_figma_client, cache_store)
        data = _parse(result)

        assert data["count"] == 1
        assert data["colors"][0]["name"] == "color/primary"
        assert data["colors"][0]["hex"].startswith("#")
        assert "css_var" in data["colors"][0]

    async def test_empty_fills_excluded(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        file_with_styles: dict[str, Any],
    ) -> None:
        # Style node with gradient fill (no SOLID) — should be excluded
        mock_figma_client.get_file.return_value = file_with_styles
        mock_figma_client.get_file_nodes.return_value = {
            "name": "x", "version": "1",
            "nodes": {"fill:1": {"document": {"fills": [{"type": "IMAGE", "imageRef": "x"}]}}},
        }
        result = await _handle_get_colors({"file_key": "KEY"}, mock_figma_client, cache_store)
        data = _parse(result)
        assert data["count"] == 0


class TestGetTypography:
    async def test_returns_typography_with_css(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        file_with_styles: dict[str, Any],
        text_style_node: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = file_with_styles
        mock_figma_client.get_file_nodes.return_value = text_style_node

        result = await _handle_get_typography({"file_key": "KEY"}, mock_figma_client, cache_store)
        data = _parse(result)

        assert data["count"] == 1
        entry = data["typography"][0]
        assert entry["name"] == "heading/h1"
        assert entry["css"]["font-size"] == "32px"
        assert entry["css"]["font-weight"] == "700"


class TestGetEffects:
    async def test_returns_effects_with_css(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        file_with_styles: dict[str, Any],
        effect_style_node: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = file_with_styles
        mock_figma_client.get_file_nodes.return_value = effect_style_node

        result = await _handle_get_effects({"file_key": "KEY"}, mock_figma_client, cache_store)
        data = _parse(result)

        assert data["count"] == 1
        assert "box-shadow" in data["effects"][0]["css"]


class TestGetSpacing:
    async def test_extracts_unique_spacing_values(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
        file_with_styles: dict[str, Any],
    ) -> None:
        mock_figma_client.get_file.return_value = file_with_styles
        result = await _handle_get_spacing({"file_key": "KEY"}, mock_figma_client, cache_store)
        data = _parse(result)

        # The fixture has itemSpacing=16, padding=24 → expect 16 and 24
        values = [t["px"] for t in data["spacing"]]
        assert 16.0 in values
        assert 24.0 in values
        assert data["count"] == len(data["spacing"])


class TestGetVariables:
    async def test_returns_collections_on_success(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        mock_figma_client.get_local_variables.return_value = {
            "status": 200,
            "error": False,
            "meta": {
                "variableCollections": {
                    "col:1": {
                        "id": "col:1",
                        "name": "Colors",
                        "modes": [{"modeId": "m:1", "name": "Default"}],
                        "defaultModeId": "m:1",
                    }
                },
                "variables": {
                    "var:1": {
                        "id": "var:1",
                        "name": "color/primary",
                        "resolvedType": "COLOR",
                        "variableCollectionId": "col:1",
                        "valuesByMode": {"m:1": {"r": 0.0, "g": 0.44, "b": 0.95, "a": 1.0}},
                        "description": "",
                    }
                },
            },
        }
        result = await _handle_get_variables({"file_key": "KEY"}, mock_figma_client, cache_store)
        data = _parse(result)

        assert data["collection_count"] == 1
        assert data["collections"][0]["name"] == "Colors"
        assert data["collections"][0]["variable_count"] == 1

    async def test_returns_error_message_on_api_failure(
        self,
        mock_figma_client: AsyncMock,
        cache_store: CacheStore,
    ) -> None:
        from figma_mcpxer.exceptions import FigmaAuthError
        mock_figma_client.get_local_variables.side_effect = FigmaAuthError()
        result = await _handle_get_variables({"file_key": "KEY"}, mock_figma_client, cache_store)
        data = _parse(result)
        assert "error" in data
