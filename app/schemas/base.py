"""Bài 100: Best Practices for Pydantic Model Design.

AppModel — base class dùng chung cho tất cả schemas trong project.
Khai báo config 1 lần ở đây, các class con kế thừa tự động áp dụng.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AppModel(BaseModel):
    """Base class với config chuẩn cho toàn bộ project.

    Tại sao cần base class thay vì set config trên từng model?
    → DRY (Don't Repeat Yourself): thay đổi 1 chỗ, áp dụng toàn bộ.
    """

    model_config = ConfigDict(
        # Bài 91 — Default Conversions / Coercion:
        # Tự động strip khoảng trắng 2 đầu cho TẤT CẢ str fields.
        # "  Clean Code  " → "Clean Code"  (không cần strip() thủ công)
        str_strip_whitespace=True,

        # Bài 100 — Best Practices:
        # validate_assignment=True → validate lại khi gán giá trị sau khi tạo.
        # book.title = ""  → ValidationError ngay thay vì lưu giá trị sai
        validate_assignment=True,

        # Bài 97 — Nested Models:
        # from_attributes=True → đọc data từ SQLAlchemy ORM object (không chỉ dict).
        # BookResponse.model_validate(db_book)  ← db_book là SQLAlchemy object
        from_attributes=True,
    )
