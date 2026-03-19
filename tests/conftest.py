"""Shared pytest fixtures for unit and integration tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.figma.client import FigmaClient


@pytest.fixture
def cache_store() -> CacheStore:
    return CacheStore(ttl_seconds=60)


@pytest.fixture
def mock_figma_client() -> AsyncMock:
    """AsyncMock that mimics FigmaClient's async interface."""
    return AsyncMock(spec=FigmaClient)


@pytest.fixture
def sample_figma_file() -> dict[str, Any]:
    """Minimal but structurally correct Figma file response payload."""
    return {
        "name": "Test Design",
        "version": "99999",
        "lastModified": "2024-01-15T10:00:00Z",
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
                            "id": "1:1",
                            "name": "Hero Frame",
                            "type": "FRAME",
                            "absoluteBoundingBox": {
                                "x": 0,
                                "y": 0,
                                "width": 1440,
                                "height": 900,
                            },
                            "children": [
                                {
                                    "id": "1:2",
                                    "name": "Title",
                                    "type": "TEXT",
                                    "characters": "Hello World",
                                    "children": None,
                                },
                                {
                                    "id": "1:3",
                                    "name": "Button",
                                    "type": "COMPONENT",
                                    "children": [],
                                },
                            ],
                        }
                    ],
                },
                {
                    "id": "0:2",
                    "name": "Components",
                    "type": "CANVAS",
                    "children": [],
                },
            ],
        },
        "components": {
            "comp-abc": {"key": "abc", "name": "Button", "description": "Primary button"}
        },
        "componentSets": {},
        "styles": {},
    }


@pytest.fixture
def sample_figma_nodes_response() -> dict[str, Any]:
    """Minimal Figma /nodes response payload."""
    return {
        "name": "Test Design",
        "version": "99999",
        "nodes": {
            "1:1": {
                "document": {
                    "id": "1:1",
                    "name": "Hero Frame",
                    "type": "FRAME",
                    "absoluteBoundingBox": {"x": 0, "y": 0, "width": 1440, "height": 900},
                    "children": [],
                },
                "components": {},
                "styles": {},
            }
        },
    }
