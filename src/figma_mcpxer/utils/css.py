"""Pure Figma-to-CSS converters.

No I/O — all functions take already-fetched Figma data dicts and return CSS strings or dicts.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Color
# ---------------------------------------------------------------------------


def figma_color_to_hex(color: dict[str, float]) -> str:
    """Convert Figma {r,g,b} (0-1 range) to #rrggbb hex string."""
    r = round(color.get("r", 0) * 255)
    g = round(color.get("g", 0) * 255)
    b = round(color.get("b", 0) * 255)
    return f"#{r:02x}{g:02x}{b:02x}"


def figma_color_to_rgba_css(color: dict[str, float], opacity: float = 1.0) -> str:
    """Convert Figma {r,g,b,a} + opacity multiplier to CSS rgba() or rgb()."""
    r = round(color.get("r", 0) * 255)
    g = round(color.get("g", 0) * 255)
    b = round(color.get("b", 0) * 255)
    a = round(color.get("a", 1.0) * opacity, 3)
    if a >= 1.0:
        return f"rgb({r}, {g}, {b})"
    return f"rgba({r}, {g}, {b}, {a})"


def fill_to_css(fill: dict[str, Any]) -> str | None:
    """Convert a single Figma fill to a CSS color/gradient string."""
    opacity = fill.get("opacity", 1.0)
    fill_type = fill.get("type")
    if fill_type == "SOLID":
        return figma_color_to_rgba_css(fill.get("color", {}), opacity)
    if fill_type in ("GRADIENT_LINEAR", "GRADIENT_RADIAL"):
        return _gradient_to_css(fill)
    return None  # IMAGE, EMOJI, VIDEO — not expressible as pure CSS


def _gradient_to_css(fill: dict[str, Any]) -> str:
    stops = fill.get("gradientStops", [])
    stops_css = ", ".join(
        f"{figma_color_to_rgba_css(s['color'])} {round(s['position'] * 100)}%"
        for s in stops
    )
    grad_type = "linear" if fill.get("type") == "GRADIENT_LINEAR" else "radial"
    return f"{grad_type}-gradient({stops_css})"


# ---------------------------------------------------------------------------
# Border radius & strokes
# ---------------------------------------------------------------------------


def border_radius_to_css(node: dict[str, Any]) -> str | None:
    """Return CSS border-radius value, or None if the node has no rounding."""
    uniform = node.get("cornerRadius")
    if uniform is not None and uniform != 0:
        return f"{uniform}px"
    radii = [
        node.get("topLeftRadius", 0),
        node.get("topRightRadius", 0),
        node.get("bottomRightRadius", 0),
        node.get("bottomLeftRadius", 0),
    ]
    if any(r != 0 for r in radii):
        return " ".join(f"{r}px" for r in radii)
    return None


def strokes_to_css(node: dict[str, Any]) -> dict[str, str]:
    """Convert Figma strokes to CSS border property (first solid stroke only)."""
    strokes = node.get("strokes", []) or []
    weight = node.get("strokeWeight", 0)
    if not strokes or not weight:
        return {}
    solid = next((s for s in strokes if s.get("type") == "SOLID" and s.get("visible", True)), None)
    if not solid:
        return {}
    color = figma_color_to_rgba_css(solid.get("color", {}))
    return {"border": f"{weight}px solid {color}"}


# ---------------------------------------------------------------------------
# Effects (shadows, blurs)
# ---------------------------------------------------------------------------


def effects_to_css(effects: list[dict[str, Any]]) -> dict[str, str]:
    """Convert Figma effects array to CSS box-shadow and filter properties."""
    shadows: list[str] = []
    filters: list[str] = []
    for effect in effects:
        if not effect.get("visible", True):
            continue
        etype = effect.get("type")
        if etype in ("DROP_SHADOW", "INNER_SHADOW"):
            shadow = _shadow_to_css(effect, inset=(etype == "INNER_SHADOW"))
            if shadow:
                shadows.append(shadow)
        elif etype == "LAYER_BLUR":
            filters.append(f"blur({effect.get('radius', 0)}px)")
    result: dict[str, str] = {}
    if shadows:
        result["box-shadow"] = ", ".join(shadows)
    if filters:
        result["filter"] = " ".join(filters)
    return result


def _shadow_to_css(effect: dict[str, Any], *, inset: bool) -> str | None:
    offset = effect.get("offset", {})
    x, y = offset.get("x", 0), offset.get("y", 0)
    radius = effect.get("radius", 0)
    spread = effect.get("spread", 0)
    color_css = figma_color_to_rgba_css(effect.get("color", {}))
    prefix = "inset " if inset else ""
    return f"{prefix}{x}px {y}px {radius}px {spread}px {color_css}"


# ---------------------------------------------------------------------------
# Auto-layout → flexbox
# ---------------------------------------------------------------------------

_JUSTIFY_MAP: dict[str, str] = {
    "MIN": "flex-start",
    "CENTER": "center",
    "MAX": "flex-end",
    "SPACE_BETWEEN": "space-between",
}
_ALIGN_MAP: dict[str, str] = {
    "MIN": "flex-start",
    "CENTER": "center",
    "MAX": "flex-end",
    "BASELINE": "baseline",
}


def auto_layout_to_css(node: dict[str, Any]) -> dict[str, str]:
    """Convert Figma auto-layout node properties to CSS flex properties."""
    layout_mode = node.get("layoutMode", "NONE")
    if layout_mode == "NONE":
        return {}
    css: dict[str, str] = {
        "display": "flex",
        "flex-direction": "column" if layout_mode == "VERTICAL" else "row",
    }
    if node.get("layoutWrap") == "WRAP":
        css["flex-wrap"] = "wrap"
    if gap := node.get("itemSpacing", 0):
        css["gap"] = f"{gap}px"
    pt = node.get("paddingTop", 0)
    pr = node.get("paddingRight", 0)
    pb = node.get("paddingBottom", 0)
    pl = node.get("paddingLeft", 0)
    if any((pt, pr, pb, pl)):
        css["padding"] = f"{pt}px {pr}px {pb}px {pl}px"
    if align := _JUSTIFY_MAP.get(node.get("primaryAxisAlignItems", "")):
        css["justify-content"] = align
    if align := _ALIGN_MAP.get(node.get("counterAxisAlignItems", "")):
        css["align-items"] = align
    return css


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

_TEXT_CASE_MAP: dict[str, str] = {
    "UPPER": "uppercase",
    "LOWER": "lowercase",
    "TITLE": "capitalize",
    "SMALL_CAPS": "small-caps",
}


def type_style_to_css(style: dict[str, Any]) -> dict[str, str]:
    """Convert a Figma text style object to CSS typography properties."""
    css: dict[str, str] = {}
    if font_family := style.get("fontFamily"):
        css["font-family"] = f'"{font_family}"'
    if font_size := style.get("fontSize"):
        css["font-size"] = f"{font_size}px"
    if font_weight := style.get("fontWeight"):
        css["font-weight"] = str(int(font_weight))
    # Line height
    lh_unit = style.get("lineHeightUnit", "INTRINSIC_%")
    if lh_unit == "PIXELS" and (lh_px := style.get("lineHeightPx")):
        css["line-height"] = f"{lh_px}px"
    elif lh_unit == "FONT_SIZE_%" and (pct := style.get("lineHeightPercentFontSize")):
        css["line-height"] = f"{pct / 100:.3f}".rstrip("0").rstrip(".")
    # Letter spacing
    ls = style.get("letterSpacing", 0)
    if ls:
        ls_unit = style.get("letterSpacingUnit", "PIXELS")
        css["letter-spacing"] = f"{ls / 100}em" if ls_unit == "PERCENT" else f"{ls}px"
    if tc := _TEXT_CASE_MAP.get(style.get("textCase", "NONE")):
        css["text-transform"] = tc
    dec = style.get("textDecoration", "NONE")
    if dec not in ("NONE", None):
        css["text-decoration"] = dec.lower().replace("_", "-")
    align = style.get("textAlignHorizontal")
    if align and align != "LEFT":
        css["text-align"] = align.lower()
    return css


# ---------------------------------------------------------------------------
# Full node CSS
# ---------------------------------------------------------------------------


def node_to_css(node: dict[str, Any], *, include_dimensions: bool = True) -> dict[str, str]:
    """Compute a best-effort CSS property map for any Figma node."""
    css: dict[str, str] = {}
    # Dimensions
    if include_dimensions:
        bbox = node.get("absoluteBoundingBox") or {}
        if bbox.get("width") is not None:
            css["width"] = f"{bbox['width']}px"
        if bbox.get("height") is not None:
            css["height"] = f"{bbox['height']}px"
    # Fills
    fills = [f for f in (node.get("fills") or []) if f.get("visible", True)]
    if fills:
        css_val = fill_to_css(fills[0])
        if css_val:
            prop = "color" if node.get("type") == "TEXT" else "background"
            css[prop] = css_val
    # Borders & radius
    css.update(strokes_to_css(node))
    if radius := border_radius_to_css(node):
        css["border-radius"] = radius
    # Effects
    css.update(effects_to_css(node.get("effects") or []))
    # Opacity
    if (op := node.get("opacity")) is not None and op != 1.0:
        css["opacity"] = f"{round(op, 3)}"
    # Auto-layout
    css.update(auto_layout_to_css(node))
    # Typography
    if node.get("type") == "TEXT":
        css.update(type_style_to_css(node.get("style") or {}))
    return css
