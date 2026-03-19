from __future__ import annotations

import pytest

from figma_mcpxer.utils.url import extract_file_key, extract_node_id, normalize_node_id


class TestExtractFileKey:
    def test_extract_from_design_url_returns_key(self) -> None:
        url = "https://www.figma.com/design/AbCdEfGhIj/My-File?node-id=1-2"
        assert extract_file_key(url) == "AbCdEfGhIj"

    def test_extract_from_file_url_returns_key(self) -> None:
        url = "https://www.figma.com/file/XyZ123/Name"
        assert extract_file_key(url) == "XyZ123"

    def test_extract_from_make_url_returns_key(self) -> None:
        url = "https://www.figma.com/make/MAKEKEY123/Name"
        assert extract_file_key(url) == "MAKEKEY123"

    def test_bare_key_passes_through(self) -> None:
        assert extract_file_key("AbCdEfGhIj") == "AbCdEfGhIj"

    def test_bare_key_is_stripped(self) -> None:
        assert extract_file_key("  AbCdEfGhIj  ") == "AbCdEfGhIj"

    def test_invalid_url_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Cannot extract file key"):
            extract_file_key("https://figma.com/unknown/path")


class TestExtractNodeId:
    def test_extract_dash_format_normalizes_to_colon(self) -> None:
        url = "https://www.figma.com/design/KEY/Name?node-id=1234-5678"
        assert extract_node_id(url) == "1234:5678"

    def test_extract_colon_format_unchanged(self) -> None:
        url = "https://www.figma.com/design/KEY/Name?node-id=1234:5678"
        assert extract_node_id(url) == "1234:5678"

    def test_url_without_node_id_returns_none(self) -> None:
        url = "https://www.figma.com/design/KEY/Name"
        assert extract_node_id(url) is None


class TestNormalizeNodeId:
    def test_dash_replaced_with_colon(self) -> None:
        assert normalize_node_id("1234-5678") == "1234:5678"

    def test_colon_format_unchanged(self) -> None:
        assert normalize_node_id("1234:5678") == "1234:5678"
