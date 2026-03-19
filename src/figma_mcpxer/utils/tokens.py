"""Converters for W3C Design Token Community Group format.

Spec: https://design-tokens.github.io/community-group/format/
"""

from __future__ import annotations

from typing import Any

from figma_mcpxer.utils.css import (
    figma_color_to_hex,
    figma_color_to_rgba_css,
)


def _token_key(name: str) -> str:
    """Normalize a Figma style name to a W3C token key (lowercase, hyphenated)."""
    return name.strip().lower().replace(" ", "-")


def color_style_to_w3c(
    fills: list[dict[str, Any]], description: str = ""
) -> dict[str, Any] | None:
    """Convert a Figma FILL style's fills array to a W3C color token."""
    solid = next((f for f in fills if f.get("type") == "SOLID" and f.get("visible", True)), None)
    if not solid:
        return None
    color = solid.get("color", {})
    opacity = solid.get("opacity", 1.0)
    value = figma_color_to_hex(color) if opacity >= 1.0 else figma_color_to_rgba_css(color, opacity)
    token: dict[str, Any] = {"$type": "color", "$value": value}
    if description:
        token["$description"] = description
    return token


def text_style_to_w3c(style: dict[str, Any], description: str = "") -> dict[str, Any]:
    """Convert a Figma text style object to a W3C typography token."""
    font_size = style.get("fontSize", 16)
    lh_unit = style.get("lineHeightUnit", "INTRINSIC_%")
    if lh_unit == "PIXELS" and (lh_px := style.get("lineHeightPx")):
        line_height = f"{lh_px}px"
    elif lh_unit == "FONT_SIZE_%" and (pct := style.get("lineHeightPercentFontSize")):
        line_height = f"{pct / 100:.3f}".rstrip("0").rstrip(".")
    else:
        line_height = "normal"

    value: dict[str, Any] = {
        "fontFamily": style.get("fontFamily", ""),
        "fontSize": f"{font_size}px",
        "fontWeight": int(style.get("fontWeight", 400)),
        "lineHeight": line_height,
    }
    ls = style.get("letterSpacing", 0)
    if ls:
        ls_unit = style.get("letterSpacingUnit", "PIXELS")
        value["letterSpacing"] = f"{ls / 100}em" if ls_unit == "PERCENT" else f"{ls}px"

    token: dict[str, Any] = {"$type": "typography", "$value": value}
    if description:
        token["$description"] = description
    return token


def effect_to_w3c(effects: list[dict[str, Any]], description: str = "") -> dict[str, Any] | None:
    """Convert a Figma EFFECT style's effects to a W3C shadow token."""
    shadow = next(
        (e for e in effects if e.get("type") == "DROP_SHADOW" and e.get("visible", True)), None
    )
    if not shadow:
        return None
    offset = shadow.get("offset", {})
    token: dict[str, Any] = {
        "$type": "shadow",
        "$value": {
            "offsetX": f"{offset.get('x', 0)}px",
            "offsetY": f"{offset.get('y', 0)}px",
            "blur": f"{shadow.get('radius', 0)}px",
            "spread": f"{shadow.get('spread', 0)}px",
            "color": figma_color_to_rgba_css(shadow.get("color", {})),
        },
    }
    if description:
        token["$description"] = description
    return token


def variable_to_w3c(variable: dict[str, Any], mode_id: str) -> dict[str, Any] | None:
    """Convert a Figma Variable to a W3C design token."""
    resolved_type = variable.get("resolvedType")
    values_by_mode = variable.get("valuesByMode", {})
    value = values_by_mode.get(mode_id)
    if value is None:
        return None

    if resolved_type == "COLOR":
        w3c_type = "color"
        w3c_value = figma_color_to_hex(value) if isinstance(value, dict) else str(value)
    elif resolved_type == "FLOAT":
        w3c_type = "dimension"
        w3c_value = f"{value}px" if isinstance(value, (int, float)) else str(value)
    elif resolved_type == "STRING":
        w3c_type = "string"
        w3c_value = str(value)
    elif resolved_type == "BOOLEAN":
        w3c_type = "boolean"
        w3c_value = bool(value)
    else:
        return None

    token: dict[str, Any] = {"$type": w3c_type, "$value": w3c_value}
    desc = variable.get("description", "")
    if desc:
        token["$description"] = desc
    return token


def build_nested_tokens(pairs: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """Build a nested W3C token tree from (name, token) pairs.

    'Color/Primary/500' → {'color': {'primary': {'500': token}}}
    """
    root: dict[str, Any] = {}
    for name, token in pairs:
        parts = [_token_key(p) for p in name.split("/")]
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = token
    return root
