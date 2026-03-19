"""In-memory TTL cache for Figma API responses.

For production with multiple replicas, swap in RedisCacheStore from
cache/redis_store.py by setting REDIS_URL in the environment.
"""

from __future__ import annotations

import time
from typing import Any


class CacheStore:
    """Async-compatible in-memory TTL cache.

    Uses async interface so callers are identical whether using memory or Redis.
    All operations are instant (no I/O) — async here is a no-op but keeps
    the interface consistent with RedisCacheStore.
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[Any, float]] = {}

    async def get(self, key: str) -> Any | None:
        """Return cached value or None if missing/expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: Any) -> None:
        """Store a value with the configured TTL."""
        self._store[key] = (value, time.monotonic() + self._ttl)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def clear(self) -> None:
        self._store.clear()

    async def size(self) -> int:
        return len(self._store)
