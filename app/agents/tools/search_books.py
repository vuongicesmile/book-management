"""Tool: search_books — tìm sách theo từ khóa trong DB.

Tool này demo cách kết nối tool với DB thật:
  1. Tạo DB session trong tool (không qua FastAPI Depends)
  2. Dùng BookRepository đã có sẵn
  3. Trả về JSON string (LLM đọc được)

## Tại sao tạo DB session trong tool?

FastAPI Depends (get_db) chỉ dùng trong request handlers.
Tool functions là coroutines thường, không chạy trong request context.
→ Phải tạo session trực tiếp từ SessionLocal.

Pattern này giống tasks.py trong RQ worker:
  db = SessionLocal()
  try:
      ...
  finally:
      db.close()
"""
from __future__ import annotations

import json
import logging

from app.agents.tools.registry import register_tool
from app.db.session import SessionLocal
from app.repositories.book import BookRepository

logger = logging.getLogger(__name__)


@register_tool(
    name="search_books",
    description=(
        "Tìm kiếm sách trong thư viện theo từ khóa trong tiêu đề hoặc mô tả. "
        "Trả về danh sách sách khớp với query. "
        "Dùng khi người dùng hỏi về sách về một chủ đề cụ thể."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Từ khóa tìm kiếm (VD: 'Python', 'machine learning', 'fiction')",
            },
            "limit": {
                "type": "integer",
                "description": "Số lượng kết quả tối đa (default 5, max 20)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
)
async def search_books(query: str, limit: int = 5) -> str:
    """Tìm sách theo keyword, trả về JSON string cho LLM đọc.

    Args:
        query: Từ khóa tìm kiếm
        limit: Số kết quả tối đa

    Returns:
        JSON string với danh sách sách, hoặc thông báo không tìm thấy
    """
    limit = min(limit, 20)  # hard cap để không query quá nhiều

    db = SessionLocal()
    try:
        all_books = BookRepository(db).search(query)
        books = all_books[:limit]

        if not books:
            return json.dumps({"found": 0, "books": [], "message": f"Không tìm thấy sách nào với từ khóa '{query}'"})

        # Chỉ trả về các field quan trọng — không dump toàn bộ ORM object
        result = {
            "found": len(books),
            "books": [
                {
                    "id": b.id,
                    "title": b.title,
                    "description": b.description or "(chưa có mô tả)",
                    "author": b.author.name if b.author else "unknown",
                }
                for b in books
            ],
        }
        logger.info("tool.search_books.result", extra={"query": query, "found": len(books)})
        return json.dumps(result, ensure_ascii=False)

    finally:
        db.close()
