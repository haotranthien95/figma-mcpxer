"""Phase 6 — Code Generation Hint Tools.

Produces structured, LLM-ready outputs designed to generate pixel-accurate UI code
from Figma designs: full CSS for a node, component descriptions with variant props,
and a complete W3C Design Token JSON export.
"""

from __future__ import annotations

import json
from typing import Any

from mcp import types

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.exceptions import ToolInputError
from figma_mcpxer.figma.client import FigmaClient
from figma_mcpxer.tools.registry import register
from figma_mcpxer.tools.shared import batch_fetch_nodes, fetch_styles_by_type
from figma_mcpxer.utils.css import node_to_css
from figma_mcpxer.utils.tokens import (
    build_nested_tokens,
    color_style_to_w3c,
    effect_to_w3c,
    text_style_to_w3c,
    variable_to_w3c,
)
from figma_mcpxer.utils.url import extract_file_key, normalize_node_id


def _text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]


# ---------------------------------------------------------------------------
# figma_get_css
# ---------------------------------------------------------------------------


def _css_block(css_props: dict[str, str]) -> str:
    """Format CSS property dict as a CSS rule block string."""
    lines = [f"  {prop}: {value};" for prop, value in css_props.items()]
    return "{\n" + "\n".join(lines) + "\n}"


async def _handle_get_css(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    node_id = normalize_node_id(arguments["node_id"])
    include_children = arguments.get("include_children", False)
    include_dimensions = arguments.get("include_dimensions", True)

    nodes = await batch_fetch_nodes(file_key, [node_id], client, cache)
    container = nodes.get(node_id)
    if not container:
        raise ToolInputError(f"Node {node_id!r} not found in file {file_key!r}")

    doc = container.get("document", {})
    css_props = node_to_css(doc, include_dimensions=include_dimensions)
    selector = f".{doc.get('name', 'node').lower().replace(' ', '-').replace('/', '__')}"

    result: dict[str, Any] = {
        "node_id": node_id,
        "node_name": doc.get("name"),
        "node_type": doc.get("type"),
        "css_properties": css_props,
        "css_block": f"{selector} {_css_block(css_props)}",
    }

    if include_children:
        children_css = []
        for child in (doc.get("children") or [])[:20]:
            child_css = node_to_css(child, include_dimensions=include_dimensions)
            if child_css:
                child_sel = f".{child.get('name', 'child').lower().replace(' ', '-')}"
                children_css.append({
                    "id": child.get("id"),
                    "name": child.get("name"),
                    "css_properties": child_css,
                    "css_block": f"{child_sel} {_css_block(child_css)}",
                })
        result["children_css"] = children_css

    return _text(result)


register(
    types.Tool(
        name="figma_get_css",
        description=(
            "Compute CSS properties for a Figma node from its design properties: "
            "background, border-radius, border, box-shadow, opacity, flexbox layout, "
            "font properties (for text nodes), and dimensions. "
            "Returns both a property dict and a ready-to-paste CSS block."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
                "node_id": {"type": "string", "description": "Node ID to compute CSS for."},
                "include_children": {
                    "type": "boolean",
                    "description": "Also compute CSS for direct children (up to 20). Default false.",  # noqa: E501
                    "default": False,
                },
                "include_dimensions": {
                    "type": "boolean",
                    "description": "Include width/height from absoluteBoundingBox. Default true.",
                    "default": True,
                },
            },
            "required": ["file_key", "node_id"],
            "additionalProperties": False,
        },
    ),
    _handle_get_css,
)

# ---------------------------------------------------------------------------
# figma_describe_component
# ---------------------------------------------------------------------------


def _variant_props_from_name(name: str) -> dict[str, str]:
    """Extract key=value pairs from a Figma variant component name like 'Size=Large, State=Hover'."""  # noqa: E501
    props: dict[str, str] = {}
    for part in name.split(","):
        if "=" in part:
            key, _, value = part.partition("=")
            props[key.strip()] = value.strip()
    return props


async def _handle_describe_component(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    node_id = normalize_node_id(arguments["node_id"])

    nodes = await batch_fetch_nodes(file_key, [node_id], client, cache)
    container = nodes.get(node_id)
    if not container:
        raise ToolInputError(f"Node {node_id!r} not found in file {file_key!r}")

    doc = container.get("document", {})
    node_type = doc.get("type", "")
    if node_type not in ("COMPONENT", "COMPONENT_SET"):
        raise ToolInputError(
            f"Node {node_id!r} is {node_type!r}, not COMPONENT or COMPONENT_SET"
        )

    prop_defs = doc.get("componentPropertyDefinitions") or {}
    children = doc.get("children") or []

    # For COMPONENT_SET, children are individual COMPONENT variants
    variants = []
    if node_type == "COMPONENT_SET":
        for child in children:
            variants.append({
                "id": child.get("id"),
                "variant_props": _variant_props_from_name(child.get("name", "")),
            })

    # Slots = named children of the component (for COMPONENT) or first variant (for COMPONENT_SET)
    slot_source = children if node_type == "COMPONENT" else (
        children[0].get("children", []) if children else []
    )
    slots = [
        {"name": c.get("name"), "type": c.get("type")}
        for c in slot_source[:20]
    ]

    result: dict[str, Any] = {
        "id": node_id,
        "name": doc.get("name"),
        "type": node_type,
        "description": doc.get("description", ""),
        "props": {
            prop: {
                "type": defn.get("type"),
                "default": defn.get("defaultValue"),
                "options": defn.get("variantOptions"),
            }
            for prop, defn in prop_defs.items()
        },
        "slots": slots,
        "variant_count": len(variants) if node_type == "COMPONENT_SET" else None,
        "variants_sample": variants[:10] if node_type == "COMPONENT_SET" else None,
        "implementation_hints": _build_implementation_hints(doc, prop_defs),
    }
    return _text(result)


def _build_implementation_hints(doc: dict[str, Any], prop_defs: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    for prop, defn in prop_defs.items():
        ptype = defn.get("type")
        if ptype == "VARIANT":
            options = defn.get("variantOptions", [])
            hints.append(f"Prop '{prop}': union type {' | '.join(repr(o) for o in options)}")
        elif ptype == "BOOLEAN":
            hints.append(f"Prop '{prop}': boolean, default {defn.get('defaultValue')}")
        elif ptype == "TEXT":
            hints.append(f"Prop '{prop}': string, default {defn.get('defaultValue')!r}")
        elif ptype == "INSTANCE_SWAP":
            hints.append(f"Prop '{prop}': ReactNode slot (INSTANCE_SWAP)")
    if doc.get("layoutMode", "NONE") != "NONE":
        hints.append("Uses auto-layout — implement with flexbox")
    return hints


register(
    types.Tool(
        name="figma_describe_component",
        description=(
            "Get a structured description of a Figma COMPONENT or COMPONENT_SET: "
            "variant props with types and options, slots (child nodes), description, "
            "and implementation hints. Use this to understand what props a component "
            "accepts before writing code."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
                "node_id": {
                    "type": "string",
                    "description": "ID of a COMPONENT or COMPONENT_SET node.",
                },
            },
            "required": ["file_key", "node_id"],
            "additionalProperties": False,
        },
    ),
    _handle_describe_component,
)

# ---------------------------------------------------------------------------
# figma_get_design_tokens_json
# ---------------------------------------------------------------------------


async def _handle_get_design_tokens_json(
    arguments: dict[str, Any], client: FigmaClient, cache: CacheStore
) -> list[types.TextContent]:
    file_key = extract_file_key(arguments["file_key"])
    include_variables = arguments.get("include_variables", True)

    # Collect all style tokens in parallel-ish (cached fetches share the same file fetch)
    fill_styles = await fetch_styles_by_type(file_key, "FILL", client, cache)
    text_styles = await fetch_styles_by_type(file_key, "TEXT", client, cache)
    effect_styles = await fetch_styles_by_type(file_key, "EFFECT", client, cache)

    color_pairs: list[tuple[str, dict[str, Any]]] = []
    for name, entry, node_doc in fill_styles:
        token = color_style_to_w3c(node_doc.get("fills") or [], entry.get("description", ""))
        if token:
            color_pairs.append((name, token))

    typo_pairs: list[tuple[str, dict[str, Any]]] = []
    for name, entry, node_doc in text_styles:
        style = node_doc.get("style") or {}
        typo_pairs.append((name, text_style_to_w3c(style, entry.get("description", ""))))

    shadow_pairs: list[tuple[str, dict[str, Any]]] = []
    for name, entry, node_doc in effect_styles:
        token = effect_to_w3c(node_doc.get("effects") or [], entry.get("description", ""))
        if token:
            shadow_pairs.append((name, token))

    token_tree: dict[str, Any] = {
        "$schema": "https://design-tokens.github.io/community-group/format/",
        "color": build_nested_tokens(color_pairs),
        "typography": build_nested_tokens(typo_pairs),
        "shadow": build_nested_tokens(shadow_pairs),
    }

    # Optionally merge Figma Variables
    if include_variables:
        try:
            raw_vars = await client.get_local_variables(file_key)
            meta = raw_vars.get("meta", {})
            cols = meta.get("variableCollections", {})
            vars_map = meta.get("variables", {})
            var_pairs: list[tuple[str, dict[str, Any]]] = []
            for col_id, col in cols.items():
                default_mode = col.get("defaultModeId", "")
                for var in vars_map.values():
                    if var.get("variableCollectionId") != col_id:
                        continue
                    w3c = variable_to_w3c(var, default_mode)
                    if w3c:
                        col_name = col.get("name", "variables")
                        var_pairs.append((f"{col_name}/{var.get('name', '')}", w3c))
            if var_pairs:
                token_tree["variables"] = build_nested_tokens(var_pairs)
        except Exception:  # noqa: BLE001 — Variables API may not be available
            token_tree["variables"] = {  # noqa: E501
                "_note": "Figma Variables unavailable (requires Professional plan)"
            }

    return _text(token_tree)


register(
    types.Tool(
        name="figma_get_design_tokens_json",
        description=(
            "Export ALL design tokens from a Figma file in W3C Design Token format: "
            "colors, typography, shadows, and optionally Figma Variables. "
            "The output can be saved as tokens.json and consumed directly by Style Dictionary, "
            "Theo, or any W3C-compatible token pipeline."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_key": {"type": "string", "description": "Figma file key or URL."},
                "include_variables": {
                    "type": "boolean",
                    "description": "Include Figma Variables if available. Default true.",
                    "default": True,
                },
            },
            "required": ["file_key"],
            "additionalProperties": False,
        },
    ),
    _handle_get_design_tokens_json,
)
