"""Phase 5 — Layout & Structure Tools.

Extracts layout properties (auto-layout, constraints, bounds, fills) from specific nodes.
These are required for generating accurate CSS that matches Figma pixel-perfectly.
"""

from __future__ import annotations

import json
from typing import Any

from mcp import types

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.exceptions import ToolInputError
from figma_mcpxer.figma.client import FigmaClient
from figma_mcpxer.tools.registry import register
from figma_mcpxer.tools.shared import batch_fetch_nodes
from figma_mcpxer.utils.css import auto_layout_to_css, fill_to_css
from figma_mcpxer.utils.url import extract_file_key, normalize_node_id


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]


def _parse_node_ids(raw_ids: list[str]) -> list[str]:
    if not raw_ids:
        raise ToolInputError("node_ids must contain at least one ID")
    return [normalize_node_id(nid) for nid in raw_ids]


async def _fetch_nodes(
    file_key: str, node_ids: list[str], client: FigmaClient, cache: CacheStore
) -> dict[str, Any]:
    return await batch_fetch_nodes(file_key, node_ids, client, cache)


# ---------------------------------------------------------------------------
# figma_get_auto_layout
# ---------------------------------------------------------------------------


def _auto_layout_info(node: dict[str, Any]) -> dict[str, Any]:
    layout_mode = node.get("layoutMode", "NONE")
    return {
        "id": node.get("id"),
        "name": node.get("name"),
        "type": node.get("type"),
        "layout_mode": layout_mode,
        "is_auto_layout": layout_mode != "NONE",
        "direction": (
            "column" if layout_mode == "VERTICAL" else "row" if layout_mode == "HORIZONTAL" else None  # noqa: E501
        ),
        "wrap": node.get("layoutWrap"),
        "gap": node.get("itemSpacing"),
        "padding": {
            "top": node.get("paddingTop", 0),
            "right": node.get("paddingRight", 0),
            "bottom": node.get("paddingBottom", 0),
            "left": node.get("paddingLeft", 0),
        },
        "primary_axis_align": node.get("primaryAxisAlignItems"),
        "counter_axis_align": node.get("counterAxisAlignItems"),
        "primary_sizing": node.get("primaryAxisSizingMode"),
        "counter_sizing": node.get("counterAxisSizingMode"),
        "css": auto_layout_to_css(node),
    }


async def _handle_get_auto_layout(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    node_ids = _parse_node_ids(arguments["node_ids"])
    nodes = await _fetch_nodes(file_key, node_ids, client, cache)

    results = [
        _auto_layout_info(container.get("document", {}))
        for nid in node_ids
        if (container := nodes.get(nid))
    ]
    return _text({"file_key": file_key, "nodes": results})


register(
    types.Tool(
        name="figma_get_auto_layout",
        description=(
            "Extract auto-layout properties (direction, gap, padding, alignment, sizing mode) "
            "for specific nodes, with CSS flex equivalents. "
            "Use this to implement accurate flexbox/grid layouts."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
                "node_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Node IDs to inspect.",
                    "minItems": 1,
                    "maxItems": 50,
                },
            },
            "required": ["file_key", "node_ids"],
            "additionalProperties": False,
        },
    ),
    _handle_get_auto_layout,
)

# ---------------------------------------------------------------------------
# figma_get_constraints
# ---------------------------------------------------------------------------


async def _handle_get_constraints(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    node_ids = _parse_node_ids(arguments["node_ids"])
    nodes = await _fetch_nodes(file_key, node_ids, client, cache)

    results = []
    for nid in node_ids:
        container = nodes.get(nid)
        if not container:
            continue
        doc = container.get("document", {})
        constraints = doc.get("constraints", {})
        results.append({
            "id": doc.get("id"),
            "name": doc.get("name"),
            "constraints": constraints,
            "hint": _constraints_hint(constraints),
        })
    return _text({"file_key": file_key, "nodes": results})


def _constraints_hint(constraints: dict[str, Any]) -> str:
    """Translate Figma constraints to a human-readable CSS positioning hint."""
    h = constraints.get("horizontal", "LEFT")
    v = constraints.get("vertical", "TOP")
    hints = []
    if h == "SCALE":
        hints.append("width: 100% (scales horizontally)")
    elif h == "LEFT_RIGHT":
        hints.append("left + right pinned (fixed margins both sides)")
    elif h == "CENTER":
        hints.append("horizontally centered")
    if v == "SCALE":
        hints.append("height: 100% (scales vertically)")
    elif v == "TOP_BOTTOM":
        hints.append("top + bottom pinned (fixed margins both sides)")
    elif v == "CENTER":
        hints.append("vertically centered")
    return "; ".join(hints) if hints else "pinned top-left (default)"


register(
    types.Tool(
        name="figma_get_constraints",
        description=(
            "Extract position constraints (horizontal/vertical) for specific nodes. "
            "Constraints define how nodes resize relative to their parent — "
            "critical for responsive layout implementation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
                "node_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 50,
                },
            },
            "required": ["file_key", "node_ids"],
            "additionalProperties": False,
        },
    ),
    _handle_get_constraints,
)

# ---------------------------------------------------------------------------
# figma_get_absolute_bounds
# ---------------------------------------------------------------------------


async def _handle_get_absolute_bounds(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    node_ids = _parse_node_ids(arguments["node_ids"])
    nodes = await _fetch_nodes(file_key, node_ids, client, cache)

    results = []
    for nid in node_ids:
        container = nodes.get(nid)
        if not container:
            continue
        doc = container.get("document", {})
        bbox = doc.get("absoluteBoundingBox") or {}
        render_bounds = doc.get("absoluteRenderBounds") or {}
        results.append({
            "id": doc.get("id"),
            "name": doc.get("name"),
            "type": doc.get("type"),
            "bounding_box": bbox,
            "render_bounds": render_bounds,
            "css": {
                "width": f"{bbox.get('width', 0)}px",
                "height": f"{bbox.get('height', 0)}px",
            },
        })
    return _text({"file_key": file_key, "nodes": results})


register(
    types.Tool(
        name="figma_get_absolute_bounds",
        description=(
            "Get absolute x/y position and width/height for specific nodes in the canvas. "
            "Use render_bounds for nodes with effects that extend beyond the bounding box."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
                "node_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 50,
                },
            },
            "required": ["file_key", "node_ids"],
            "additionalProperties": False,
        },
    ),
    _handle_get_absolute_bounds,
)

# ---------------------------------------------------------------------------
# figma_get_fills
# ---------------------------------------------------------------------------


def _describe_fill(fill: dict[str, Any]) -> dict[str, Any]:
    fill_type = fill.get("type", "UNKNOWN")
    css_val = fill_to_css(fill)
    result: dict[str, Any] = {
        "type": fill_type,
        "visible": fill.get("visible", True),
        "opacity": fill.get("opacity", 1.0),
        "blend_mode": fill.get("blendMode"),
        "css": css_val,
    }
    if fill_type == "SOLID":
        result["color"] = fill.get("color")
    elif "GRADIENT" in fill_type:
        result["gradient_stops"] = fill.get("gradientStops")
    elif fill_type == "IMAGE":
        result["image_ref"] = fill.get("imageRef")
        result["scale_mode"] = fill.get("scaleMode")
    return result


async def _handle_get_fills(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    node_ids = _parse_node_ids(arguments["node_ids"])
    nodes = await _fetch_nodes(file_key, node_ids, client, cache)

    results = []
    for nid in node_ids:
        container = nodes.get(nid)
        if not container:
            continue
        doc = container.get("document", {})
        fills = doc.get("fills") or []
        results.append({
            "id": doc.get("id"),
            "name": doc.get("name"),
            "type": doc.get("type"),
            "fill_count": len(fills),
            "fills": [_describe_fill(f) for f in fills],
        })
    return _text({"file_key": file_key, "nodes": results})


register(
    types.Tool(
        name="figma_get_fills",
        description=(
            "Extract all fill layers (solid colors, gradients, images) for specific nodes. "
            "Returns fill type, opacity, blend mode, and CSS-ready color/gradient values."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
                "node_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Node IDs to inspect.",
                    "minItems": 1,
                    "maxItems": 50,
                },
            },
            "required": ["file_key", "node_ids"],
            "additionalProperties": False,
        },
    ),
    _handle_get_fills,
)
