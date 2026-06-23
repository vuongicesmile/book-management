"""Bài 158+162: RQ Worker entry point.

Chạy song song với FastAPI server:
  Terminal 1: uvicorn app.main:app --reload      ← HTTP server
  Terminal 2: python worker.py                   ← background worker

Hoặc Docker:
  docker compose up --scale worker=3             ← 3 workers song song

Worker lifecycle:
  1. Connect tới Redis
  2. Lắng nghe queue "rag-indexing"
  3. Khi có job → dequeue → chạy function → lưu result vào Redis
  4. Lặp lại (vô tận)

Scale (bài 162):
  Mỗi worker = 1 process = 1 job tại 1 thời điểm.
  Muốn xử lý N jobs song song → chạy N workers.
"""
from __future__ import annotations

import logging
import sys

from redis import Redis
from rq import Queue, Worker

from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    conn = Redis.from_url(settings.redis_url)

    # Test connection
    try:
        conn.ping()
        logger.info("worker.redis.connected", extra={"url": settings.redis_url})
    except Exception as e:
        logger.error("worker.redis.connection_failed", extra={"error": str(e)})
        sys.exit(1)

    queues = [Queue(settings.rag_queue_name, connection=conn)]
    logger.info("worker.starting", extra={"queues": [q.name for q in queues]})

    worker = Worker(queues, connection=conn)
    worker.work(with_scheduler=True)  # with_scheduler: hỗ trợ scheduled jobs
