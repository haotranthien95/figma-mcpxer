"""Integration tests — hit the real Figma API.

These tests are skipped automatically when FIGMA_TEST_FILE_KEY is not set.
To run them:
  FIGMA_ACCESS_TOKEN=<token> FIGMA_TEST_FILE_KEY=<key> pytest tests/integration/ -v
"""

from __future__ import annotations

import pytest

from figma_mcpxer.config import get_settings
from figma_mcpxer.figma.client import FigmaClient


@pytest.fixture
def settings():  # type: ignore[no-untyped-def]
    return get_settings()


@pytest.fixture
def figma_client(settings):  # type: ignore[no-untyped-def]
    return FigmaClient(
        access_token=settings.figma_access_token,
        base_url=settings.figma_api_base_url,
    )


def _require_test_file_key() -> str:
    settings = get_settings()
    if not settings.figma_test_file_key:
        pytest.skip("FIGMA_TEST_FILE_KEY not set — skipping integration test")
    return settings.figma_test_file_key


class TestFigmaClientIntegration:
    async def test_get_file_returns_document(self, figma_client: FigmaClient) -> None:
        file_key = _require_test_file_key()
        async with figma_client:
            result = await figma_client.get_file(file_key, depth=1)
        assert "document" in result
        assert result["document"]["type"] == "DOCUMENT"

    async def test_get_file_pages_are_canvas_nodes(self, figma_client: FigmaClient) -> None:
        file_key = _require_test_file_key()
        async with figma_client:
            result = await figma_client.get_file(file_key, depth=1)
        pages = result["document"].get("children", [])
        assert len(pages) > 0
        for page in pages:
            assert page["type"] == "CANVAS"

    async def test_get_file_nodes_returns_requested_node(
        self, figma_client: FigmaClient
    ) -> None:
        file_key = _require_test_file_key()
        async with figma_client:
            file_data = await figma_client.get_file(file_key, depth=1)
            pages = file_data["document"].get("children", [])
            if not pages:
                pytest.skip("No pages found in test file")
            first_page_id = pages[0]["id"]
            nodes_data = await figma_client.get_file_nodes(file_key, [first_page_id])
        assert first_page_id in nodes_data["nodes"]
