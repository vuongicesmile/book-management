"""CSV Import schemas — minh hoạ bài 97, 98, 99, 101.

Bài 97: Nested Models — CSVImportRequest chứa list[BookImportRow]
Bài 99: Advanced Nested Patterns — @model_validator cross-list validation
Bài 101: model_dump — exclude, include, mode="json"
"""
from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from app.schemas.base import AppModel


# ── Bài 97: Nested Models ─────────────────────────────────────────────────────
# BookImportRow là model nhỏ, được nhúng vào CSVImportRequest dưới dạng list.

class BookImportRow(AppModel):
    """1 dòng trong file CSV import.

    Bài 97: Nested Models — class nhỏ dùng làm item trong list của class lớn.
    """
    title: str = Field(min_length=1, max_length=255, strip_whitespace=True)
    author_id: int = Field(gt=0)
    category_id: int = Field(gt=0)
    published_year: int | None = Field(default=None, ge=1000, le=2100)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("title", mode="before")
    @classmethod
    def title_not_whitespace(cls, v: str) -> str:
        if isinstance(v, str) and not v.strip():
            raise ValueError("title không được rỗng")
        return v.strip().title()


# ── Bài 99: Advanced Nested Patterns ─────────────────────────────────────────
# CSVImportRequest chứa list[BookImportRow] — list of nested models.
# @model_validator validate TOÀN BỘ list (cross-item validation).

class CSVImportRequest(AppModel):
    """Request body khi import nhiều books cùng lúc.

    Bài 97: Nested Models
        books: list[BookImportRow] — list chứa nested model

    Bài 99: Advanced Nested Patterns
        @model_validator kiểm tra điều kiện trên toàn bộ list:
        - Ít nhất 1 book
        - Không có title trùng nhau

    Bài 101: model_dump
        request.model_dump()
        # {
        #   "books": [
        #     {"title": "Clean Code", "author_id": 1, ...},  ← nested dict
        #     {"title": "Pragmatic Programmer", ...}
        #   ],
        #   "overwrite_existing": False
        # }

        request.model_dump(include={"books"})  ← chỉ lấy field "books"
        request.model_dump_json(indent=2)      ← JSON string đẹp
    """
    # list[BookImportRow] → Pydantic tự validate từng item trong list
    books: list[BookImportRow] = Field(
        min_length=1,
        description="Danh sách books cần import, tối thiểu 1 item",
    )
    overwrite_existing: bool = Field(
        default=False,
        description="True → ghi đè book đã tồn tại. False → bỏ qua.",
    )

    # Bài 99: @model_validator trên toàn bộ list (cross-item)
    # Không thể làm bằng @field_validator vì cần nhìn thấy tất cả items cùng lúc.
    @model_validator(mode="after")
    def no_duplicate_titles(self) -> "CSVImportRequest":
        """Không cho phép có 2 books trùng title trong cùng 1 request.

        Bài 99: Advanced Nested Patterns — validate cross-item trong list.
        """
        titles = [book.title for book in self.books]
        seen: set[str] = set()
        duplicates: list[str] = []

        for title in titles:
            if title in seen:
                duplicates.append(title)
            seen.add(title)

        if duplicates:
            raise ValueError(
                f"Có title bị trùng trong danh sách import: {duplicates}"
            )
        return self

    @model_validator(mode="after")
    def max_import_limit(self) -> "CSVImportRequest":
        """Giới hạn tối đa 500 books mỗi lần import.

        Bài 99: Có thể stack nhiều @model_validator — chạy theo thứ tự khai báo.
        """
        if len(self.books) > 500:
            raise ValueError(
                f"Tối đa 500 books mỗi lần import, bạn gửi {len(self.books)}"
            )
        return self
