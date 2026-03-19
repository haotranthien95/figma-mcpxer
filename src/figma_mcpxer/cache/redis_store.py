"""Redis-backed cache store for production deployments.

Requires the optional `redis` extra: pip install figma-mcpxer[redis]

Usage: set REDIS_URL=redis://localhost:6379/0 and the server
will automatically switch from the in-memory CacheStore to this.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class RedisCacheStore:
    """Async Redis cache with the same interface as CacheStore.

    Values are JSON-serialised, so only JSON-compatible data can be stored.
    The TTL is applied per key via Redis SETEX.
    """

    def __init__(self, ttl_seconds: int, redis_url: str) -> None:
        # Import lazily so the package is optional at install time
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:
            raise ImportError(
                "Redis support requires: pip install figma-mcpxer[redis]"
            ) from exc

        self._ttl = ttl_seconds
        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    async def get(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Cache key %r contained invalid JSON — ignoring", key)
            return None

    async def set(self, key: str, value: Any) -> None:
        await self._redis.setex(key, self._ttl, json.dumps(value))

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def clear(self) -> None:
        # FLUSHDB would clear the whole DB — use a key pattern instead
        keys = await self._redis.keys("*")
        if keys:
            await self._redis.delete(*keys)

    async def size(self) -> int:
        return await self._redis.dbsize()

    async def close(self) -> None:
        await self._redis.aclose()
