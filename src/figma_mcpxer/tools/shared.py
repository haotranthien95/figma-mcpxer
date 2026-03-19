"""Shared helpers used by multiple tool modules.

These functions coordinate API calls and caching — they are not pure utilities
(those live in utils/). Tool modules import from here to avoid duplication.
"""

from __future__ import annotations

from typing import Any

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.figma.client import FigmaClient


async def fetch_file_cached(
    file_key: str,
    client: FigmaClient,
    cache: CacheStore,
    *,
    depth: int | None = None,
) -> dict[str, Any]:
    """Fetch a Figma file, using the cache when available."""
    cache_key = f"file:{file_key}:depth:{depth}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    data = await client.get_file(file_key, depth=depth)
    cache.set(cache_key, data)
    return data  # type: ignore[return-value]


async def batch_fetch_nodes(
    file_key: str,
    node_ids: list[str],
    client: FigmaClient,
    cache: CacheStore,
    *,
    batch_size: int = 50,
) -> dict[str, Any]:
    """Fetch nodes in batches of batch_size to stay within URL length limits.

    Returns a merged {node_id: node_container} dict.
    """
    all_nodes: dict[str, Any] = {}
    for i in range(0, len(node_ids), batch_size):
        batch = node_ids[i : i + batch_size]
        cache_key = f"nodes:{file_key}:{','.join(sorted(batch))}"
        batch_data: dict[str, Any] | None = cache.get(cache_key)
        if batch_data is None:
            batch_data = await client.get_file_nodes(file_key, batch)
            cache.set(cache_key, batch_data)
        all_nodes.update(batch_data.get("nodes", {}))
    return all_nodes


async def fetch_styles_by_type(
    file_key: str,
    style_type: str,
    client: FigmaClient,
    cache: CacheStore,
) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Return (name, style_entry, node_document) tuples for a given styleType.

    Steps:
      1. Get file (cached) → .styles dict: {node_id: {name, styleType, ...}}
      2. Filter by style_type
      3. Batch-fetch those style nodes to get their visual properties
    """
    file_data = await fetch_file_cached(file_key, client, cache, depth=None)
    styles_index: dict[str, Any] = file_data.get("styles", {})

    filtered = {
        nid: entry
        for nid, entry in styles_index.items()
        if entry.get("styleType") == style_type
    }
    if not filtered:
        return []

    nodes = await batch_fetch_nodes(file_key, list(filtered.keys()), client, cache)

    result: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for node_id, style_entry in filtered.items():
        node_doc = nodes.get(node_id, {}).get("document", {})
        result.append((style_entry.get("name", ""), style_entry, node_doc))
    return result
