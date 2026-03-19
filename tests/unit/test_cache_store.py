from __future__ import annotations

import asyncio

from figma_mcpxer.cache.store import CacheStore


class TestCacheStore:
    async def test_set_and_get_returns_value(self) -> None:
        store = CacheStore(ttl_seconds=60)
        await store.set("key", {"data": 42})
        assert await store.get("key") == {"data": 42}

    async def test_get_missing_key_returns_none(self) -> None:
        store = CacheStore(ttl_seconds=60)
        assert await store.get("nonexistent") is None

    async def test_expired_entry_returns_none(self) -> None:
        store = CacheStore(ttl_seconds=0)
        await store.set("key", "value")
        # TTL=0 means immediately expired on next access
        await asyncio.sleep(0.01)
        assert await store.get("key") is None

    async def test_delete_removes_entry(self) -> None:
        store = CacheStore(ttl_seconds=60)
        await store.set("key", "value")
        await store.delete("key")
        assert await store.get("key") is None

    async def test_delete_nonexistent_key_does_not_raise(self) -> None:
        store = CacheStore(ttl_seconds=60)
        await store.delete("ghost")  # must not raise

    async def test_clear_removes_all_entries(self) -> None:
        store = CacheStore(ttl_seconds=60)
        await store.set("a", 1)
        await store.set("b", 2)
        await store.clear()
        assert await store.size() == 0

    async def test_size_reflects_live_entries(self) -> None:
        store = CacheStore(ttl_seconds=60)
        assert await store.size() == 0
        await store.set("x", 1)
        assert await store.size() == 1
