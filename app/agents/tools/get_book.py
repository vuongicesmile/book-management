"""Tool: get_book — lấy thông tin chi tiết một cuốn sách theo ID.

Dùng khi agent đã có book_id (từ search_books hoặc user cung cấp)
và cần đọc thêm thông tin trước khi trả lời.
"""
from __future__ import annotations

import json
import logging

from app.agents.tools.registry import register_tool
from app.db.session import SessionLocal
from app.repositories.book import BookRepository

logger = logging.getLogger(__name__)


@register_tool(
    name="get_book",
    description=(
        "Lấy thông tin đầy đủ của một cuốn sách theo ID. "
        "Dùng khi đã biết book_id và cần thêm chi tiết như description, category."
    ),
    parameters={
        "type": "object",
        "properties": {
            "book_id": {
                "type": "integer",
                "description": "ID của sách cần lấy thông tin",
            },
        },
        "required": ["book_id"],
    },
)
async def get_book(book_id: int) -> str:
    """Lấy chi tiết một cuốn sách, trả về JSON string.

    Args:
        book_id: ID sách cần lấy

    Returns:
        JSON string với đầy đủ thông tin sách
    """
    db = SessionLocal()
    try:
        book = BookRepository(db).get(book_id)

        if not book:
            return json.dumps({"error": f"Không tìm thấy sách với id={book_id}"})

        result = {
            "id": book.id,
            "title": book.title,
            "description": book.description or "(chưa có mô tả)",
            "author": book.author.name if book.author else "unknown",
            "categories": [c.name for c in book.categories] if hasattr(book, "categories") and book.categories else [],
        }
        logger.info("tool.get_book.result", extra={"book_id": book_id, "title": book.title})
        return json.dumps(result, ensure_ascii=False)

    finally:
        db.close()
