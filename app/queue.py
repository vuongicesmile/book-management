"""Redis Queue setup — bài 155-158.

Học từ vuonglearning pattern:
  - vuonglearning dùng FastAPI background_tasks (fire-and-forget, same process)
  - book-management dùng RQ (separate worker process, persistent queue)
  - RQ phù hợp hơn cho RAG indexing vì có thể mất 5 phút

Tại sao RQ thay vì background_tasks?
  background_tasks: chạy trong FastAPI process → vẫn bị ảnh hưởng nếu server restart
  RQ: chạy trong worker process riêng → server restart không ảnh hưởng job
"""
from __future__ import annotations

from functools import lru_cache

from redis import Redis
from rq import Queue

from app.core.config import settings


@lru_cache(maxsize=1)
def get_redis_sync() -> Redis:
    """Sync Redis client dùng cho RQ (RQ không dùng asyncio)."""
    return Redis.from_url(settings.redis_url)


@lru_cache(maxsize=1)
def get_rag_queue() -> Queue:
    """RQ Queue cho RAG indexing jobs."""
    return Queue(settings.rag_queue_name, connection=get_redis_sync())
