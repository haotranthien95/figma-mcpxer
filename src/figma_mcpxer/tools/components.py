"""Phase 4 — Component & Asset Tools.

Provides MCP tools for inspecting Figma components, component sets, styles,
and exporting node images or resolving image fill URLs.
"""

from __future__ import annotations

import json
from typing import Any

from mcp import types

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.exceptions import ToolInputError
from figma_mcpxer.figma.client import FigmaClient
from figma_mcpxer.tools.registry import register
from figma_mcpxer.tools.shared import batch_fetch_nodes, fetch_file_cached
from figma_mcpxer.utils.url import extract_file_key, normalize_node_id


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]


# ---------------------------------------------------------------------------
# figma_get_components
# ---------------------------------------------------------------------------


async def _handle_get_components(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    include_details = arguments.get("include_details", False)

    file_data = await fetch_file_cached(file_key, client, cache, depth=None)
    components_index: dict[str, Any] = file_data.get("components", {})
    component_sets_index: dict[str, Any] = file_data.get("componentSets", {})

    components = []
    if include_details and components_index:
        node_ids = list(components_index.keys())
        nodes = await batch_fetch_nodes(file_key, node_ids, client, cache)
        for node_id, meta in components_index.items():
            doc = nodes.get(node_id, {}).get("document", {})
            comp_set_id = doc.get("componentSetId")
            comp_set_entry = component_sets_index.get(comp_set_id, {}) if comp_set_id else {}
            comp_set_name = comp_set_entry.get("name")
            components.append({
                "id": node_id,
                "name": meta.get("name"),
                "description": meta.get("description", ""),
                "component_set": comp_set_name,
                "property_definitions": doc.get("componentPropertyDefinitions"),
                "children_summary": [
                    {"name": c.get("name"), "type": c.get("type")}
                    for c in (doc.get("children") or [])[:10]
                ],
            })
    else:
        for node_id, meta in components_index.items():
            components.append({
                "id": node_id,
                "name": meta.get("name"),
                "description": meta.get("description", ""),
            })

    return _text({
        "file_key": file_key,
        "count": len(components),
        "components": components,
    })


register(
    types.Tool(
        name="figma_get_components",
        description=(
            "List all local components in a Figma file. "
            "Set include_details=true to also get property definitions and children summary — "
            "useful for understanding what props a component accepts."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
                "include_details": {
                    "type": "boolean",
                    "description": "Fetch full node data for each component (slower). Default false.",  # noqa: E501
                    "default": False,
                },
            },
            "required": ["file_key"],
            "additionalProperties": False,
        },
    ),
    _handle_get_components,
)

# ---------------------------------------------------------------------------
# figma_get_component_sets
# ---------------------------------------------------------------------------


async def _handle_get_component_sets(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    file_data = await fetch_file_cached(file_key, client, cache, depth=None)
    component_sets_index: dict[str, Any] = file_data.get("componentSets", {})

    if not component_sets_index:
        return _text({"file_key": file_key, "count": 0, "component_sets": []})

    nodes = await batch_fetch_nodes(file_key, list(component_sets_index.keys()), client, cache)

    sets = []
    for node_id, meta in component_sets_index.items():
        doc = nodes.get(node_id, {}).get("document", {})
        prop_defs = doc.get("componentPropertyDefinitions") or {}
        variant_count = len(doc.get("children") or [])
        sets.append({
            "id": node_id,
            "name": meta.get("name"),
            "description": meta.get("description", ""),
            "variant_count": variant_count,
            "property_definitions": {
                prop: {
                    "type": defn.get("type"),
                    "default": defn.get("defaultValue"),
                    "options": defn.get("variantOptions"),
                }
                for prop, defn in prop_defs.items()
            },
        })
    return _text({"file_key": file_key, "count": len(sets), "component_sets": sets})


register(
    types.Tool(
        name="figma_get_component_sets",
        description=(
            "List all component sets (multi-variant components) in a Figma file. "
            "Returns variant properties and options — essential for generating components "
            "with correct prop types (e.g. size: 'sm'|'md'|'lg', disabled: boolean)."
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
    _handle_get_component_sets,
)

# ---------------------------------------------------------------------------
# figma_get_styles
# ---------------------------------------------------------------------------


async def _handle_get_styles(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    file_data = await fetch_file_cached(file_key, client, cache, depth=None)
    styles_index: dict[str, Any] = file_data.get("styles", {})

    grouped: dict[str, list[dict[str, Any]]] = {}
    for node_id, entry in styles_index.items():
        style_type = entry.get("styleType", "UNKNOWN")
        grouped.setdefault(style_type, []).append({
            "id": node_id,
            "name": entry.get("name"),
            "description": entry.get("description", ""),
        })

    return _text({
        "file_key": file_key,
        "total": len(styles_index),
        "by_type": {k: {"count": len(v), "styles": v} for k, v in grouped.items()},
    })


register(
    types.Tool(
        name="figma_get_styles",
        description=(
            "List all styles defined in a Figma file grouped by type (FILL, TEXT, EFFECT, GRID). "
            "Use figma_get_colors / figma_get_typography / figma_get_effects for details."
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
    _handle_get_styles,
)

# ---------------------------------------------------------------------------
# figma_export_image
# ---------------------------------------------------------------------------


async def _handle_export_image(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    node_id = normalize_node_id(arguments["node_id"])
    fmt = arguments.get("format", "png")
    scale = float(arguments.get("scale", 1.0))
    use_abs_bounds = arguments.get("use_absolute_bounds", False)

    if fmt not in ("png", "svg", "jpg", "pdf"):
        raise ToolInputError(f"format must be one of: png, svg, jpg, pdf — got {fmt!r}")
    if not (0.01 <= scale <= 4.0):
        raise ToolInputError("scale must be between 0.01 and 4.0")

    result = await client.export_images(
        file_key, [node_id], format=fmt, scale=scale, use_absolute_bounds=use_abs_bounds
    )
    images: dict[str, Any] = result.get("images", {})
    url = images.get(node_id)
    return _text({"node_id": node_id, "format": fmt, "scale": scale, "url": url})


register(
    types.Tool(
        name="figma_export_image",
        description=(
            "Export a single Figma node as a PNG, SVG, JPG, or PDF image URL. "
            "Returns a CDN URL valid for ~30 days. Use for icons, illustrations, or screenshots."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
                "node_id": {"type": "string", "description": "Node ID to export (e.g. '1:2')."},
                "format": {
                    "type": "string",
                    "enum": ["png", "svg", "jpg", "pdf"],
                    "description": "Image format. Default: png.",
                    "default": "png",
                },
                "scale": {
                    "type": "number",
                    "description": "Export scale (0.01–4.0). Default: 1.0 (1x).",
                    "default": 1.0,
                },
                "use_absolute_bounds": {
                    "type": "boolean",
                    "description": "Use absolute bounds instead of bounding box. Default: false.",
                    "default": False,
                },
            },
            "required": ["file_key", "node_id"],
            "additionalProperties": False,
        },
    ),
    _handle_export_image,
)

# ---------------------------------------------------------------------------
# figma_export_images
# ---------------------------------------------------------------------------


async def _handle_export_images(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    raw_ids: list[str] = arguments["node_ids"]
    fmt = arguments.get("format", "png")
    scale = float(arguments.get("scale", 1.0))

    if not raw_ids:
        raise ToolInputError("node_ids must not be empty")
    node_ids = [normalize_node_id(nid) for nid in raw_ids]
    result = await client.export_images(file_key, node_ids, format=fmt, scale=scale)
    return _text({"format": fmt, "scale": scale, "images": result.get("images", {})})


register(
    types.Tool(
        name="figma_export_images",
        description=(
            "Export multiple Figma nodes as images in a single API call. "
            "Returns a map of node_id → CDN URL. More efficient than repeated figma_export_image calls."  # noqa: E501
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
                "node_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of node IDs to export.",
                    "minItems": 1,
                    "maxItems": 100,
                },
                "format": {
                    "type": "string",
                    "enum": ["png", "svg", "jpg", "pdf"],
                    "default": "png",
                },
                "scale": {"type": "number", "default": 1.0},
            },
            "required": ["file_key", "node_ids"],
            "additionalProperties": False,
        },
    ),
    _handle_export_images,
)

# ---------------------------------------------------------------------------
# figma_get_images
# ---------------------------------------------------------------------------


async def _handle_get_images(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    cache_key = f"image_fills:{file_key}"
    raw: dict[str, Any] | None = await cache.get(cache_key)
    if raw is None:
        raw = await client.get_file_image_fills(file_key)
        await cache.set(cache_key, raw)

    images = raw.get("meta", {}).get("images", {})
    return _text({
        "file_key": file_key,
        "count": len(images),
        "note": "Maps imageRef keys (found in node fills of type IMAGE) to CDN URLs.",
        "images": images,
    })


register(
    types.Tool(
        name="figma_get_images",
        description=(
            "Resolve all image fill references in a Figma file to CDN URLs. "
            "Use this when nodes have fills of type IMAGE — the imageRef maps to these URLs."
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
    _handle_get_images,
)
