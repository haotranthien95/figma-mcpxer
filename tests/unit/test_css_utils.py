"""Tests for utils/css.py — all pure functions, no I/O."""

from __future__ import annotations

from figma_mcpxer.utils.css import (
    auto_layout_to_css,
    border_radius_to_css,
    effects_to_css,
    figma_color_to_hex,
    figma_color_to_rgba_css,
    fill_to_css,
    node_to_css,
    strokes_to_css,
    type_style_to_css,
)


class TestColorConverters:
    def test_opaque_color_to_hex(self) -> None:
        assert figma_color_to_hex({"r": 1.0, "g": 0.0, "b": 0.0}) == "#ff0000"

    def test_black_to_hex(self) -> None:
        assert figma_color_to_hex({"r": 0.0, "g": 0.0, "b": 0.0}) == "#000000"

    def test_white_to_hex(self) -> None:
        assert figma_color_to_hex({"r": 1.0, "g": 1.0, "b": 1.0}) == "#ffffff"

    def test_opaque_color_to_rgb(self) -> None:
        result = figma_color_to_rgba_css({"r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0})
        assert result == "rgb(255, 0, 0)"

    def test_transparent_color_to_rgba(self) -> None:
        result = figma_color_to_rgba_css({"r": 0.0, "g": 0.0, "b": 0.0, "a": 0.5})
        assert "rgba" in result
        assert "0.5" in result

    def test_opacity_multiplied_with_alpha(self) -> None:
        result = figma_color_to_rgba_css({"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0}, opacity=0.5)
        assert "rgba" in result


class TestFillToCss:
    def test_solid_fill_returns_rgb(self) -> None:
        fill = {"type": "SOLID", "color": {"r": 0.0, "g": 0.0, "b": 1.0, "a": 1.0}}
        result = fill_to_css(fill)
        assert result == "rgb(0, 0, 255)"

    def test_linear_gradient_returns_linear_gradient(self) -> None:
        fill = {
            "type": "GRADIENT_LINEAR",
            "gradientStops": [
                {"color": {"r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0}, "position": 0.0},
                {"color": {"r": 0.0, "g": 0.0, "b": 1.0, "a": 1.0}, "position": 1.0},
            ],
        }
        result = fill_to_css(fill)
        assert result is not None
        assert "linear-gradient" in result

    def test_image_fill_returns_none(self) -> None:
        fill = {"type": "IMAGE", "imageRef": "abc123"}
        assert fill_to_css(fill) is None


class TestBorderRadius:
    def test_uniform_radius(self) -> None:
        assert border_radius_to_css({"cornerRadius": 8}) == "8px"

    def test_per_corner_radius(self) -> None:
        node = {"topLeftRadius": 4, "topRightRadius": 8, "bottomRightRadius": 4, "bottomLeftRadius": 8}
        result = border_radius_to_css(node)
        assert result is not None
        assert "4px" in result and "8px" in result

    def test_no_radius_returns_none(self) -> None:
        assert border_radius_to_css({}) is None

    def test_zero_radius_returns_none(self) -> None:
        assert border_radius_to_css({"cornerRadius": 0}) is None


class TestEffects:
    def test_drop_shadow_to_box_shadow(self) -> None:
        effects = [{
            "type": "DROP_SHADOW",
            "visible": True,
            "offset": {"x": 0, "y": 4},
            "radius": 8,
            "spread": 0,
            "color": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 0.25},
        }]
        result = effects_to_css(effects)
        assert "box-shadow" in result
        assert "0px 4px 8px" in result["box-shadow"]

    def test_invisible_effect_skipped(self) -> None:
        effects = [{"type": "DROP_SHADOW", "visible": False}]
        result = effects_to_css(effects)
        assert "box-shadow" not in result

    def test_layer_blur_to_filter(self) -> None:
        effects = [{"type": "LAYER_BLUR", "visible": True, "radius": 4}]
        result = effects_to_css(effects)
        assert "filter" in result
        assert "blur(4px)" in result["filter"]


class TestAutoLayout:
    def test_horizontal_layout_returns_flex_row(self) -> None:
        node = {"layoutMode": "HORIZONTAL", "itemSpacing": 8}
        css = auto_layout_to_css(node)
        assert css["display"] == "flex"
        assert css["flex-direction"] == "row"
        assert css["gap"] == "8px"

    def test_vertical_layout_returns_flex_column(self) -> None:
        node = {"layoutMode": "VERTICAL", "itemSpacing": 16}
        css = auto_layout_to_css(node)
        assert css["flex-direction"] == "column"

    def test_no_layout_returns_empty(self) -> None:
        assert auto_layout_to_css({"layoutMode": "NONE"}) == {}

    def test_padding_included(self) -> None:
        node = {
            "layoutMode": "HORIZONTAL",
            "paddingTop": 10,
            "paddingRight": 20,
            "paddingBottom": 10,
            "paddingLeft": 20,
        }
        css = auto_layout_to_css(node)
        assert "padding" in css


class TestTypeStyle:
    def test_font_size_and_family(self) -> None:
        style = {"fontFamily": "Inter", "fontSize": 16, "fontWeight": 400}
        css = type_style_to_css(style)
        assert css["font-family"] == '"Inter"'
        assert css["font-size"] == "16px"
        assert css["font-weight"] == "400"

    def test_letter_spacing_pixels(self) -> None:
        style = {"letterSpacing": 2, "letterSpacingUnit": "PIXELS"}
        css = type_style_to_css(style)
        assert css["letter-spacing"] == "2px"

    def test_text_case_upper(self) -> None:
        style = {"textCase": "UPPER"}
        css = type_style_to_css(style)
        assert css["text-transform"] == "uppercase"


class TestNodeToCss:
    def test_text_node_color_not_background(self) -> None:
        node = {
            "type": "TEXT",
            "fills": [{"type": "SOLID", "color": {"r": 0, "g": 0, "b": 0, "a": 1}, "visible": True}],
        }
        css = node_to_css(node, include_dimensions=False)
        assert "color" in css
        assert "background" not in css

    def test_frame_node_gets_background(self) -> None:
        node = {
            "type": "FRAME",
            "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1, "a": 1}, "visible": True}],
        }
        css = node_to_css(node, include_dimensions=False)
        assert "background" in css

    def test_dimensions_included_when_requested(self) -> None:
        node = {"type": "FRAME", "absoluteBoundingBox": {"width": 400, "height": 200}}
        css = node_to_css(node, include_dimensions=True)
        assert css["width"] == "400px"
        assert css["height"] == "200px"
