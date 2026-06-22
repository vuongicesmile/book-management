"""Background notification tasks cho book management.

Dùng async def để có thể gọi qua asyncio.create_task() — giống vuonglearning.

vuonglearning pattern:
    task = asyncio.create_task(notify_func(...))

book-management:
    asyncio.create_task(notify_book_created(...))

Cả 2 đều fire-and-forget — response trả về ngay, task chạy sau trên event loop.
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def notify_book_created(book_id: int, title: str, author_id: int) -> None:
    """Notification khi book mới được tạo.

    async def → có thể await bên trong (gọi HTTP, gửi email, v.v.)
    Hiện tại dùng asyncio.sleep(0) để yield control về event loop —
    minh hoạ đây là coroutine thực sự, không block.
    """
    await asyncio.sleep(0)  # yield control — giống "non-blocking checkpoint"
    logger.info(
        "notification.book.created",
        extra={
            "book_id": book_id,
            "title": title,
            "author_id": author_id,
        },
    )


async def notify_book_deleted(book_id: int) -> None:
    """Notification khi book bị xóa."""
    await asyncio.sleep(0)
    logger.info(
        "notification.book.deleted",
        extra={"book_id": book_id},
    )


async def notify_books_imported(created: int, skipped: int, titles: list[str]) -> None:
    """Notification khi import CSV xong.

    Trong thực tế: gọi webhook, gửi email summary, v.v.
    """
    await asyncio.sleep(0)
    logger.info(
        "notification.book.imported",
        extra={
            "created_count": created,
            "skipped_count": skipped,
            "sample_titles": titles[:3],
        },
    )
