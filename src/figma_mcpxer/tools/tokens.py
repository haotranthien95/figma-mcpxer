"""Phase 3 — Design Token Tools.

Extracts design tokens (colors, typography, spacing, effects, variables, grids)
required for generating pixel-accurate UI code that matches the Figma design.
"""

from __future__ import annotations

import json
from typing import Any

from mcp import types

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.exceptions import FigmaAPIError
from figma_mcpxer.figma.client import FigmaClient
from figma_mcpxer.tools.registry import register
from figma_mcpxer.tools.shared import fetch_file_cached, fetch_styles_by_type
from figma_mcpxer.utils.css import (
    effects_to_css,
    figma_color_to_hex,
    figma_color_to_rgba_css,
    type_style_to_css,
)
from figma_mcpxer.utils.url import extract_file_key


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]


def _css_var_name(prefix: str, name: str) -> str:
    return f"--{prefix}-" + name.lower().replace("/", "-").replace(" ", "-")


# ---------------------------------------------------------------------------
# figma_get_colors
# ---------------------------------------------------------------------------


async def _handle_get_colors(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    styles = await fetch_styles_by_type(file_key, "FILL", client, cache)

    colors = []
    for name, style_entry, node_doc in styles:
        fills = node_doc.get("fills") or []
        solid = next(
            (f for f in fills if f.get("type") == "SOLID" and f.get("visible", True)), None
        )
        if not solid:
            continue
        color = solid.get("color", {})
        opacity = solid.get("opacity", 1.0)
        colors.append({
            "name": name,
            "hex": figma_color_to_hex(color),
            "rgba": figma_color_to_rgba_css(color, opacity),
            "css_var": _css_var_name("color", name),
            "opacity": opacity,
            "description": style_entry.get("description", ""),
        })
    return _text({"file_key": file_key, "count": len(colors), "colors": colors})


register(
    types.Tool(
        name="figma_get_colors",
        description=(
            "Extract all color styles from a Figma file with hex, rgba, and CSS variable "
            "name suggestions. Use these instead of hardcoding colors when building UI."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
            },
            "required": ["file_key"],
            "additionalProperties": False,
        },
    ),
    _handle_get_colors,
)

# ---------------------------------------------------------------------------
# figma_get_typography
# ---------------------------------------------------------------------------


async def _handle_get_typography(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    styles = await fetch_styles_by_type(file_key, "TEXT", client, cache)

    type_styles = []
    for name, style_entry, node_doc in styles:
        style = node_doc.get("style") or {}
        type_styles.append({
            "name": name,
            "description": style_entry.get("description", ""),
            "properties": {
                "fontFamily": style.get("fontFamily"),
                "fontSize": style.get("fontSize"),
                "fontWeight": style.get("fontWeight"),
                "lineHeightPx": style.get("lineHeightPx"),
                "lineHeightUnit": style.get("lineHeightUnit"),
                "letterSpacing": style.get("letterSpacing"),
                "textCase": style.get("textCase"),
                "textDecoration": style.get("textDecoration"),
            },
            "css": type_style_to_css(style),
        })
    return _text({"file_key": file_key, "count": len(type_styles), "typography": type_styles})


register(
    types.Tool(
        name="figma_get_typography",
        description=(
            "Extract all text styles from a Figma file with font family, size, weight, "
            "line-height, letter-spacing, and ready-to-use CSS properties."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
            },
            "required": ["file_key"],
            "additionalProperties": False,
        },
    ),
    _handle_get_typography,
)

# ---------------------------------------------------------------------------
# figma_get_effects
# ---------------------------------------------------------------------------


async def _handle_get_effects(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    styles = await fetch_styles_by_type(file_key, "EFFECT", client, cache)

    effect_styles = []
    for name, style_entry, node_doc in styles:
        effects = node_doc.get("effects") or []
        effect_styles.append({
            "name": name,
            "description": style_entry.get("description", ""),
            "effects": effects,
            "css": effects_to_css(effects),
        })
    return _text({"file_key": file_key, "count": len(effect_styles), "effects": effect_styles})


register(
    types.Tool(
        name="figma_get_effects",
        description=(
            "Extract all effect styles (shadows, blurs) from a Figma file. "
            "Returns raw Figma effect data and CSS-ready box-shadow/filter values."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
            },
            "required": ["file_key"],
            "additionalProperties": False,
        },
    ),
    _handle_get_effects,
)

# ---------------------------------------------------------------------------
# figma_get_grids
# ---------------------------------------------------------------------------


async def _handle_get_grids(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    styles = await fetch_styles_by_type(file_key, "GRID", client, cache)

    grid_styles = [
        {
            "name": name,
            "description": style_entry.get("description", ""),
            "grids": node_doc.get("layoutGrids") or [],
        }
        for name, style_entry, node_doc in styles
    ]
    return _text({"file_key": file_key, "count": len(grid_styles), "grids": grid_styles})


register(
    types.Tool(
        name="figma_get_grids",
        description=(
            "Extract layout grid styles (columns, rows, gutters, offsets) from a Figma file."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
            },
            "required": ["file_key"],
            "additionalProperties": False,
        },
    ),
    _handle_get_grids,
)

# ---------------------------------------------------------------------------
# figma_get_spacing
# ---------------------------------------------------------------------------


def _collect_spacing(node: dict[str, Any], values: set[float]) -> None:
    """Iterative DFS: collect unique spacing values from auto-layout nodes."""
    stack = [node]
    while stack:
        cur = stack.pop()
        if cur.get("layoutMode", "NONE") != "NONE":
            spacing_keys = ("itemSpacing", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft")  # noqa: E501
            for key in spacing_keys:
                if (val := cur.get(key)) and val > 0:
                    values.add(float(val))
        for child in cur.get("children", []) or []:
            stack.append(child)


async def _handle_get_spacing(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    file_data = await fetch_file_cached(file_key, client, cache, depth=None)

    spacing: set[float] = set()
    _collect_spacing(file_data.get("document", {}), spacing)

    tokens = [
        {"px": v, "css": f"{v}px", "rem": f"{v / 16:.3f}".rstrip("0").rstrip(".")}
        for v in sorted(spacing)
    ]
    return _text({
        "file_key": file_key,
        "count": len(tokens),
        "note": "Unique gap/padding values from all auto-layout nodes in the file.",
        "spacing": tokens,
    })


register(
    types.Tool(
        name="figma_get_spacing",
        description=(
            "Extract unique spacing values (gap, padding) from all auto-layout nodes in the file. "
            "Returns a sorted list in px and rem to inform your spacing scale."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
            },
            "required": ["file_key"],
            "additionalProperties": False,
        },
    ),
    _handle_get_spacing,
)

# ---------------------------------------------------------------------------
# figma_get_variables
# ---------------------------------------------------------------------------


async def _handle_get_variables(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    cache_key = f"variables:{file_key}"
    raw: dict[str, Any] | None = cache.get(cache_key)
    if raw is None:
        try:
            raw = await client.get_local_variables(file_key)
            cache.set(cache_key, raw)
        except FigmaAPIError as exc:
            return _text({
                "error": str(exc),
                "note": "Figma Variables API requires Figma Professional plan or higher.",
            })

    meta = raw.get("meta", {})
    cols_raw = meta.get("variableCollections", {})
    vars_raw = meta.get("variables", {})

    collections = []
    for col_id, col in cols_raw.items():
        variables_in_col = [
            {
                "id": var_id,
                "name": var.get("name"),
                "type": var.get("resolvedType"),
                "values": var.get("valuesByMode", {}),
                "description": var.get("description", ""),
            }
            for var_id, var in vars_raw.items()
            if var.get("variableCollectionId") == col_id
        ]
        collections.append({
            "id": col_id,
            "name": col.get("name"),
            "modes": col.get("modes", []),
            "default_mode_id": col.get("defaultModeId", ""),
            "variable_count": len(variables_in_col),
            "variables": variables_in_col,
        })
    return _text({
        "file_key": file_key,
        "collection_count": len(collections),
        "collections": collections,
    })


register(
    types.Tool(
        name="figma_get_variables",
        description=(
            "Fetch Figma Variables (COLOR, FLOAT, STRING, BOOLEAN) with all mode values. "
            "Requires Figma Professional plan. Returns a clear error if unavailable."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
            },
            "required": ["file_key"],
            "additionalProperties": False,
        },
    ),
    _handle_get_variables,
)
