"""Bài 158-160: RQ Task functions — chạy trong worker process.

QUAN TRỌNG: Functions ở đây phải là top-level importable.
RQ serialize function path (app.ai.rag.tasks.index_book_pdf_task) vào Redis,
worker process import lại rồi chạy. Lambda hay nested function → KHÔNG dùng được.

Tại sao asyncio.run()?
  RQ worker là sync (không phải asyncio event loop).
  Service functions là async def → cần asyncio.run() để chạy trong sync context.
  Học từ pattern: nếu cần async-native worker → dùng ARQ thay RQ.
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


def index_book_pdf_task(book_id: int, file_bytes: bytes, filename: str) -> dict:
    """Bài 158: Worker task — index PDF vào ChromaDB.

    Chạy trong RQ worker process (không phải FastAPI).
    asyncio.run() vì service functions là async.
    """
    from app.ai.rag import service
    from app.db.session import SessionLocal

    logger.info("rag.task.index.start", extra={"book_id": book_id, "filename": filename})
    db = SessionLocal()
    try:
        result = asyncio.run(service.index_book_pdf(book_id, file_bytes, filename, db))
        logger.info("rag.task.index.done", extra={"book_id": book_id})
        return result.model_dump()
    finally:
        db.close()


def rag_summarize_task(book_id: int) -> dict:
    """Async RAG summarize — chạy trong worker khi cần summarize lớn."""
    from app.ai.rag import service
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        result = asyncio.run(service.rag_summarize(book_id, db))
        return result.model_dump()
    finally:
        db.close()
