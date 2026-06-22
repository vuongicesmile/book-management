"""Prompt templates — tách riêng khỏi logic.

Pattern từ ilmuchat: ai_proxy/prompts.py chứa tất cả prompt strings.
Lợi ích:
  - Dễ chỉnh sửa prompt mà không cần đụng vào logic
  - Dễ test từng prompt riêng lẻ
  - Tái sử dụng prompt qua nhiều tasks
"""
from __future__ import annotations


def build_summarize_prompt(title: str, author: str, description: str | None) -> str:
    """Prompt tóm tắt sách thành 2-3 câu."""
    return f"""Tóm tắt cuốn sách sau trong 2-3 câu ngắn gọn bằng tiếng Việt.

Tên sách: {title}
Tác giả: {author}
Mô tả: {description or "Không có mô tả"}

Chỉ trả về phần tóm tắt, không thêm tiêu đề hay giải thích."""


def build_generate_description_prompt(title: str, author: str, category: str) -> str:
    """Prompt viết description cho sách chưa có mô tả."""
    return f"""Viết mô tả ngắn gọn (3-4 câu) cho cuốn sách sau bằng tiếng Việt.
Mô tả nên hấp dẫn và thông tin về nội dung sách.

Tên sách: {title}
Tác giả: {author}
Thể loại: {category}

Chỉ trả về phần mô tả, không thêm gì khác."""


def build_embedding_text(title: str, description: str | None) -> str:
    """Tạo text input cho embedding từ title + description.

    Càng nhiều context → embedding càng chính xác.
    Giới hạn 8000 ký tự để không vượt token limit.
    """
    text = title
    if description:
        text += f". {description}"
    return text[:8000]
