from __future__ import annotations

import time

from figma_mcpxer.cache.store import CacheStore


class TestCacheStore:
    def test_set_and_get_returns_value(self) -> None:
        store = CacheStore(ttl_seconds=60)
        store.set("key", {"data": 42})
        assert store.get("key") == {"data": 42}

    def test_get_missing_key_returns_none(self) -> None:
        store = CacheStore(ttl_seconds=60)
        assert store.get("nonexistent") is None

    def test_expired_entry_returns_none(self) -> None:
        store = CacheStore(ttl_seconds=0)
        store.set("key", "value")
        # TTL=0 means immediately expired on next access
        time.sleep(0.01)
        assert store.get("key") is None

    def test_delete_removes_entry(self) -> None:
        store = CacheStore(ttl_seconds=60)
        store.set("key", "value")
        store.delete("key")
        assert store.get("key") is None

    def test_delete_nonexistent_key_does_not_raise(self) -> None:
        store = CacheStore(ttl_seconds=60)
        store.delete("ghost")  # must not raise

    def test_clear_removes_all_entries(self) -> None:
        store = CacheStore(ttl_seconds=60)
        store.set("a", 1)
        store.set("b", 2)
        store.clear()
        assert store.size() == 0

    def test_size_reflects_live_entries(self) -> None:
        store = CacheStore(ttl_seconds=60)
        assert store.size() == 0
        store.set("x", 1)
        assert store.size() == 1
