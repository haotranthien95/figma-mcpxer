"""Tests for utils/tokens.py — W3C design token converters."""

from __future__ import annotations

from figma_mcpxer.utils.tokens import (
    build_nested_tokens,
    color_style_to_w3c,
    effect_to_w3c,
    text_style_to_w3c,
    variable_to_w3c,
)


class TestColorStyleToW3c:
    def test_solid_fill_returns_color_token(self) -> None:
        fills = [{"type": "SOLID", "color": {"r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0}, "visible": True}]
        token = color_style_to_w3c(fills)
        assert token is not None
        assert token["$type"] == "color"
        assert token["$value"] == "#ff0000"

    def test_transparent_fill_uses_rgba(self) -> None:
        fills = [{"type": "SOLID", "color": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 1.0}, "opacity": 0.5, "visible": True}]
        token = color_style_to_w3c(fills)
        assert token is not None
        assert "rgba" in token["$value"]

    def test_no_solid_fill_returns_none(self) -> None:
        fills = [{"type": "IMAGE", "imageRef": "abc", "visible": True}]
        assert color_style_to_w3c(fills) is None

    def test_description_included_when_present(self) -> None:
        fills = [{"type": "SOLID", "color": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0}, "visible": True}]
        token = color_style_to_w3c(fills, description="White background")
        assert token is not None
        assert token["$description"] == "White background"


class TestTextStyleToW3c:
    def test_basic_typography_token(self) -> None:
        style = {
            "fontFamily": "Inter",
            "fontSize": 16,
            "fontWeight": 400,
        }
        token = text_style_to_w3c(style)
        assert token["$type"] == "typography"
        assert token["$value"]["fontFamily"] == "Inter"
        assert token["$value"]["fontSize"] == "16px"
        assert token["$value"]["fontWeight"] == 400

    def test_pixel_line_height(self) -> None:
        style = {"fontFamily": "A", "fontSize": 16, "fontWeight": 400,
                 "lineHeightUnit": "PIXELS", "lineHeightPx": 24}
        token = text_style_to_w3c(style)
        assert token["$value"]["lineHeight"] == "24px"


class TestEffectToW3c:
    def test_drop_shadow_returns_shadow_token(self) -> None:
        effects = [{
            "type": "DROP_SHADOW",
            "visible": True,
            "offset": {"x": 0, "y": 4},
            "radius": 8,
            "spread": 0,
            "color": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 0.12},
        }]
        token = effect_to_w3c(effects)
        assert token is not None
        assert token["$type"] == "shadow"
        assert token["$value"]["blur"] == "8px"

    def test_no_drop_shadow_returns_none(self) -> None:
        effects = [{"type": "LAYER_BLUR", "visible": True, "radius": 4}]
        assert effect_to_w3c(effects) is None


class TestVariableToW3c:
    def test_color_variable(self) -> None:
        var = {
            "resolvedType": "COLOR",
            "valuesByMode": {"mode1": {"r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0}},
        }
        token = variable_to_w3c(var, "mode1")
        assert token is not None
        assert token["$type"] == "color"

    def test_float_variable(self) -> None:
        var = {"resolvedType": "FLOAT", "valuesByMode": {"mode1": 8.0}}
        token = variable_to_w3c(var, "mode1")
        assert token is not None
        assert token["$type"] == "dimension"
        assert token["$value"] == "8.0px"

    def test_missing_mode_returns_none(self) -> None:
        var = {"resolvedType": "COLOR", "valuesByMode": {}}
        assert variable_to_w3c(var, "nonexistent") is None


class TestBuildNestedTokens:
    def test_flat_name_goes_to_root(self) -> None:
        pairs = [("primary", {"$type": "color", "$value": "#ff0000"})]
        result = build_nested_tokens(pairs)
        assert "primary" in result

    def test_slash_creates_nested_groups(self) -> None:
        pairs = [("Color/Primary/500", {"$type": "color", "$value": "#ff0000"})]
        result = build_nested_tokens(pairs)
        assert "color" in result
        assert "primary" in result["color"]
        assert "500" in result["color"]["primary"]

    def test_multiple_tokens_merged_correctly(self) -> None:
        pairs = [
            ("Color/Primary", {"$type": "color", "$value": "#ff0000"}),
            ("Color/Secondary", {"$type": "color", "$value": "#00ff00"}),
        ]
        result = build_nested_tokens(pairs)
        assert "primary" in result["color"]
        assert "secondary" in result["color"]
