"""Tool: summarize_book — tóm tắt nội dung sách dùng AI.

Tool này gọi lại service layer đã có sẵn (app.ai.service.summarize),
demo cách agent tái sử dụng existing business logic.

## Tại sao gọi service thay vì gọi thẳng OpenAI?

service.summarize() đã có:
  - Cache (Redis): gọi lần 2 trả ngay, không tốn OpenAI token
  - Rate limiting: đã được handle ở router layer
  - Error handling: AINotConfiguredError, book not found
  - Logging: structured logs

Nếu tool gọi thẳng OpenAI → duplicate code, bỏ qua cache, không log đúng.
"""
from __future__ import annotations

import json
import logging

from app.agents.tools.registry import register_tool
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


@register_tool(
    name="summarize_book",
    description=(
        "Tạo tóm tắt AI cho một cuốn sách theo ID. "
        "Dùng khi người dùng muốn biết nội dung chính của sách. "
        "Yêu cầu book_id cụ thể — dùng search_books trước nếu chưa có ID."
    ),
    parameters={
        "type": "object",
        "properties": {
            "book_id": {
                "type": "integer",
                "description": "ID của sách cần tóm tắt",
            },
        },
        "required": ["book_id"],
    },
)
async def summarize_book(book_id: int) -> str:
    """Tóm tắt sách dùng AI, trả về JSON string với summary.

    Tái sử dụng app.ai.service.summarize() — có cache, logging đầy đủ.

    Args:
        book_id: ID sách cần tóm tắt

    Returns:
        JSON string với summary hoặc lỗi
    """
    # Import lazy để tránh circular import
    from app.ai import service as ai_service

    db = SessionLocal()
    try:
        response = await ai_service.summarize(book_id, db)
        result = {
            "book_id": book_id,
            "title": response.title,
            "summary": response.summary,
        }
        logger.info("tool.summarize_book.done", extra={"book_id": book_id})
        return json.dumps(result, ensure_ascii=False)

    except Exception as exc:
        logger.error("tool.summarize_book.error", extra={"book_id": book_id, "error": str(exc)})
        return json.dumps({"error": f"Không thể tóm tắt sách {book_id}: {exc}"})

    finally:
        db.close()
