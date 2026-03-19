"""Unit tests for FigmaClient — all HTTP calls are intercepted by respx."""

from __future__ import annotations

from typing import Any

import pytest
import respx
from httpx import Response

from figma_mcpxer.exceptions import FigmaAPIError, FigmaAuthError, FigmaNotFoundError
from figma_mcpxer.figma.client import FigmaClient

BASE_URL = "https://api.figma.com/v1"
FILE_KEY = "TestKey123"


@pytest.fixture
def client() -> FigmaClient:
    return FigmaClient(access_token="test-token", base_url=BASE_URL)


class TestGetFile:
    @respx.mock
    async def test_get_file_returns_parsed_json(
        self, client: FigmaClient, sample_figma_file: dict[str, Any]
    ) -> None:
        respx.get(f"{BASE_URL}/files/{FILE_KEY}").mock(
            return_value=Response(200, json=sample_figma_file)
        )
        result = await client.get_file(FILE_KEY)
        assert result["name"] == "Test Design"

    @respx.mock
    async def test_get_file_with_depth_sends_param(self, client: FigmaClient) -> None:
        route = respx.get(f"{BASE_URL}/files/{FILE_KEY}").mock(
            return_value=Response(200, json={"name": "X", "document": {}, "version": "1",
                                             "lastModified": "2024-01-01", "schemaVersion": 0})
        )
        await client.get_file(FILE_KEY, depth=2)
        assert route.called
        assert "depth=2" in str(route.calls[0].request.url)

    @respx.mock
    async def test_get_file_404_raises_not_found(self, client: FigmaClient) -> None:
        respx.get(f"{BASE_URL}/files/{FILE_KEY}").mock(return_value=Response(404))
        with pytest.raises(FigmaNotFoundError):
            await client.get_file(FILE_KEY)

    @respx.mock
    async def test_get_file_403_raises_auth_error(self, client: FigmaClient) -> None:
        respx.get(f"{BASE_URL}/files/{FILE_KEY}").mock(return_value=Response(403))
        with pytest.raises(FigmaAuthError):
            await client.get_file(FILE_KEY)

    @respx.mock
    async def test_get_file_500_raises_api_error(self, client: FigmaClient) -> None:
        respx.get(f"{BASE_URL}/files/{FILE_KEY}").mock(
            return_value=Response(500, text="Internal error")
        )
        with pytest.raises(FigmaAPIError) as exc_info:
            await client.get_file(FILE_KEY)
        assert exc_info.value.status_code == 500


class TestGetFileNodes:
    @respx.mock
    async def test_get_nodes_returns_node_map(
        self, client: FigmaClient, sample_figma_nodes_response: dict[str, Any]
    ) -> None:
        respx.get(f"{BASE_URL}/files/{FILE_KEY}/nodes").mock(
            return_value=Response(200, json=sample_figma_nodes_response)
        )
        result = await client.get_file_nodes(FILE_KEY, ["1:1"])
        assert "nodes" in result
        assert "1:1" in result["nodes"]

    @respx.mock
    async def test_get_nodes_joins_ids_with_comma(self, client: FigmaClient) -> None:
        from urllib.parse import unquote
        route = respx.get(f"{BASE_URL}/files/{FILE_KEY}/nodes").mock(
            return_value=Response(200, json={"name": "X", "version": "1", "nodes": {}})
        )
        await client.get_file_nodes(FILE_KEY, ["1:1", "2:2"])
        assert route.called
        url = unquote(str(route.calls[0].request.url))
        assert "1:1" in url and "2:2" in url
