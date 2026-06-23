"""Redis client và cache helpers — học từ pattern vuonglearning.

Pattern vuonglearning (services/vuonglearning-api/src/common/redis.py):
  - PrefixedRedis wrapper để isolate preview environments
  - Chỉ expose operations thật sự dùng (không __getattr__ passthrough)
  - cache_get / cache_set / cache_delete là building blocks cho mọi nơi

Book-management version: đơn giản hơn (không cần multi-tenant prefix),
nhưng cùng concept và cùng interface.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Client singleton ───────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _make_client() -> aioredis.Redis:
    """Tạo Redis client 1 lần duy nhất — reuse connection pool."""
    return aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )


def get_redis() -> aioredis.Redis:
    return _make_client()


# ── Key builder ────────────────────────────────────────────────────────────────

def cache_key(*parts: str | int) -> str:
    """Build namespaced cache key.

    Học từ vuonglearning: ilmu:user:42, ilmu:flags:defaults
    Book-management: bm:book:42, bm:ai:summary:42
    """
    return "bm:" + ":".join(str(p) for p in parts)


# ── CRUD helpers ───────────────────────────────────────────────────────────────

async def cache_get(key: str) -> Any | None:
    """Đọc từ Redis, deserialize JSON. None nếu miss hoặc Redis down."""
    try:
        r = get_redis()
        raw = await r.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        logger.warning("redis.cache_get.error", extra={"key": key})
        return None  # fail-open: cache miss, không crash app


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    """Lưu vào Redis dưới dạng JSON với TTL (giây)."""
    try:
        r = get_redis()
        await r.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        logger.warning("redis.cache_set.error", extra={"key": key})
        # Best-effort — không fail request nếu Redis down


async def cache_delete(key: str) -> None:
    """Xóa cache entry — gọi khi data thay đổi (invalidate)."""
    try:
        r = get_redis()
        await r.delete(key)
    except Exception:
        logger.warning("redis.cache_delete.error", extra={"key": key})
