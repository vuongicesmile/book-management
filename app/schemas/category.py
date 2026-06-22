"""Schemas cho Category — minh hoạ bài 97, 98, 99.

Bài 97: Nested Models — CategoryWithBooks chứa list[BookSummary]
Bài 98: Self-Referencing Models — Category có children: list[Category]
Bài 99: Advanced Nested Patterns — CategoryTree với đệ quy nhiều cấp
"""
from __future__ import annotations

from pydantic import Field, field_validator

from app.schemas.base import AppModel


class CategoryBase(AppModel):
    name: str = Field(min_length=1, max_length=100, description="Tên danh mục")
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def name_must_not_be_whitespace(cls, v: str) -> str:
        if isinstance(v, str) and not v.strip():
            raise ValueError("name không được chỉ có khoảng trắng")
        return v


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(AppModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class Category(CategoryBase):
    id: int


# ── Bài 98: Self-Referencing Models ──────────────────────────────────────────
#
# Model tự tham chiếu chính nó — dùng cho cấu trúc cây (tree).
# Category có thể chứa sub-categories (con, cháu, ...).
#
# Ví dụ:
#   Programming
#   ├── Python
#   │   ├── FastAPI
#   │   └── Django
#   └── JavaScript
#
# children: list[CategoryTree] = []  ← tự tham chiếu
#
# Cần `from __future__ import annotations` ở đầu file để Python
# không báo lỗi "CategoryTree chưa được định nghĩa" khi đọc type hint.

class CategoryTree(AppModel):
    """Category dạng cây, có thể chứa sub-categories đệ quy.

    Bài 98: Self-Referencing Models
    """
    id: int
    name: str
    description: str | None = None

    # Bài 98: Self-referencing
    # list[CategoryTree] — list chứa chính class này
    # = [] → default empty list (không có con)
    children: list[CategoryTree] = []

    @property
    def depth(self) -> int:
        """Đếm độ sâu của cây đệ quy."""
        if not self.children:
            return 0
        return 1 + max(child.depth for child in self.children)


# ── Bài 97: Nested Models ─────────────────────────────────────────────────────
#
# Model chứa model khác — dùng khi cần trả về data liên quan cùng lúc.
# Thay vì trả category_id=1, trả về cả object Category đầy đủ.

class BookSummary(AppModel):
    """Summary nhỏ gọn của Book — dùng bên trong CategoryWithBooks.

    Bài 97: Nested Models — class nhỏ để nhúng vào class lớn hơn.
    Không import Book từ book.py để tránh circular import.
    """
    id: int
    title: str
    published_year: int | None = None


class CategoryWithBooks(Category):
    """Category kèm danh sách books thuộc category đó.

    Bài 97: Nested Models
    CategoryWithBooks chứa list[BookSummary] — model lồng trong model.

    Ví dụ response:
    {
        "id": 1,
        "name": "Programming",
        "books": [
            {"id": 1, "title": "Clean Code", "published_year": 2008},
            {"id": 2, "title": "The Pragmatic Programmer", "published_year": 1999}
        ]
    }
    """
    # Bài 99: Advanced Nested Patterns
    # list[BookSummary] — list chứa nested model
    # default_factory=list → mỗi instance có list riêng (không share)
    books: list[BookSummary] = Field(default_factory=list)

    @property
    def book_count(self) -> int:
        return len(self.books)
