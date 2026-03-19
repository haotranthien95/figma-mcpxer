"""Unit tests for Phase 9 — Production Hardening infrastructure."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from figma_mcpxer.cache.store import CacheStore
from figma_mcpxer.middleware.rate_limit import RateLimitMiddleware


# ---------------------------------------------------------------------------
# CacheStore (async interface)
# ---------------------------------------------------------------------------


class TestCacheStoreAsync:
    async def test_set_and_get_returns_value(self) -> None:
        store = CacheStore(ttl_seconds=60)
        await store.set("key", {"value": 42})
        result = await store.get("key")
        assert result == {"value": 42}

    async def test_get_missing_key_returns_none(self) -> None:
        store = CacheStore(ttl_seconds=60)
        assert await store.get("nonexistent") is None

    async def test_expired_entry_returns_none(self) -> None:
        store = CacheStore(ttl_seconds=0)  # TTL = 0 → expires immediately
        await store.set("key", "data")
        # Force monotonic time to advance past TTL
        await asyncio.sleep(0.01)
        assert await store.get("key") is None

    async def test_delete_removes_entry(self) -> None:
        store = CacheStore(ttl_seconds=60)
        await store.set("key", "data")
        await store.delete("key")
        assert await store.get("key") is None

    async def test_delete_missing_key_is_no_op(self) -> None:
        store = CacheStore(ttl_seconds=60)
        await store.delete("never-existed")  # should not raise

    async def test_clear_empties_store(self) -> None:
        store = CacheStore(ttl_seconds=60)
        await store.set("a", 1)
        await store.set("b", 2)
        await store.clear()
        assert await store.size() == 0

    async def test_size_reflects_live_entries(self) -> None:
        store = CacheStore(ttl_seconds=60)
        await store.set("x", 1)
        await store.set("y", 2)
        assert await store.size() == 2


# ---------------------------------------------------------------------------
# RateLimitMiddleware — unit test the _allow() logic directly
# ---------------------------------------------------------------------------


class TestRateLimitAllow:
    def _make_middleware(self, max_rps: int) -> RateLimitMiddleware:
        # Pass a minimal fake app — we only call _allow() directly
        return RateLimitMiddleware(app=None, max_rps=max_rps)  # type: ignore[arg-type]

    def test_requests_within_limit_are_allowed(self) -> None:
        mw = self._make_middleware(max_rps=5)
        for _ in range(5):
            assert mw._allow("10.0.0.1") is True

    def test_request_exceeding_limit_is_denied(self) -> None:
        mw = self._make_middleware(max_rps=3)
        for _ in range(3):
            mw._allow("10.0.0.2")
        # 4th request in same 1-second window should be denied
        assert mw._allow("10.0.0.2") is False

    def test_different_ips_have_independent_buckets(self) -> None:
        mw = self._make_middleware(max_rps=1)
        assert mw._allow("1.1.1.1") is True
        assert mw._allow("2.2.2.2") is True  # different IP — own bucket
        # Second request for first IP is denied
        assert mw._allow("1.1.1.1") is False

    def test_window_resets_after_one_second(self) -> None:
        mw = self._make_middleware(max_rps=1)
        assert mw._allow("10.0.0.3") is True
        assert mw._allow("10.0.0.3") is False

        # Manually shift timestamps into the past to simulate window expiry
        bucket = mw._windows["10.0.0.3"]
        bucket[0] = bucket[0] - 1.1  # move the timestamp > 1 sec into the past

        assert mw._allow("10.0.0.3") is True  # window reset, should be allowed


# ---------------------------------------------------------------------------
# RedisCacheStore — tested with fakeredis (no real Redis server required)
# ---------------------------------------------------------------------------


class TestRedisCacheStoreWithFakeredis:
    @pytest.fixture
    async def redis_store(self) -> Any:
        """Create a RedisCacheStore backed by fakeredis."""
        import fakeredis.aioredis as fake_aioredis

        from figma_mcpxer.cache.redis_store import RedisCacheStore

        store = RedisCacheStore.__new__(RedisCacheStore)
        store._ttl = 60
        store._redis = fake_aioredis.FakeRedis(decode_responses=True)
        return store

    async def test_set_and_get_roundtrip(self, redis_store: Any) -> None:
        await redis_store.set("test_key", {"color": "#fff"})
        result = await redis_store.get("test_key")
        assert result == {"color": "#fff"}

    async def test_get_missing_returns_none(self, redis_store: Any) -> None:
        assert await redis_store.get("missing") is None

    async def test_delete_removes_key(self, redis_store: Any) -> None:
        await redis_store.set("del_me", 42)
        await redis_store.delete("del_me")
        assert await redis_store.get("del_me") is None

    async def test_clear_removes_all_keys(self, redis_store: Any) -> None:
        await redis_store.set("a", 1)
        await redis_store.set("b", 2)
        await redis_store.clear()
        assert await redis_store.get("a") is None
        assert await redis_store.get("b") is None
