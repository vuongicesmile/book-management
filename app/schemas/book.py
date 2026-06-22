"""Schemas cho Book — minh hoạ tổng hợp bài 90→101.

Bài 90: Foundation — BaseModel, type annotations
Bài 91: Default Conversions — str_strip_whitespace, int coercion
Bài 92: Mixing pydantic + typing — int | None, list
Bài 93: Field constraints — min_length, max_length, ge, le
Bài 94: @field_validator + @model_validator
Bài 95: @computed_field — age, display_name
Bài 96: Advanced Validation — Annotated custom type
Bài 97: Nested Models — author: Author, category: Category
Bài 100: Best Practices — tách Create/Update/Response
Bài 101: model_dump / model_dump_json — exclude_unset, exclude
"""
from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, Field, computed_field, field_validator, model_validator

from app.schemas.author import Author
from app.schemas.base import AppModel
from app.schemas.category import Category


# ── Bài 96: Advanced Validation — Annotated custom type ───────────────────────
#
# Annotated[type, validator] → đóng gói type + validator thành 1 type mới.
# Tái sử dụng được — dùng ở nhiều class mà không lặp lại validator.
#
# Cách dùng:
#   NormalizedTitle = Annotated[str, AfterValidator(normalize_title)]
#   title: NormalizedTitle  ← tự normalize mọi nơi dùng type này
#
# Khác với @field_validator:
#   @field_validator → gắn với 1 class cụ thể
#   Annotated         → tái sử dụng qua nhiều class

def _normalize_title(v: str) -> str:
    """Chuẩn hóa title: strip + Title Case.

    "  clean code  " → "Clean Code"
    """
    return v.strip().title()


# Bài 96: Annotated custom type — NormalizedTitle tự normalize ở bất kỳ đâu dùng
NormalizedTitle = Annotated[str, AfterValidator(_normalize_title)]


class BookBase(AppModel):
    # Bài 93: Field constraints
    # NormalizedTitle (Bài 96) → tự normalize trước khi validate
    # min_length=1 → sau khi normalize, vẫn không được rỗng
    title: NormalizedTitle = Field(
        min_length=1,
        max_length=255,
        description="Tên sách — tự chuẩn hoá về Title Case",
    )

    # Bài 92: int | None = None → optional integer
    # Bài 93: ge=1000 (>=1000), le=2100 (<=2100)
    published_year: int | None = Field(
        default=None,
        ge=1000,
        le=2100,
        description="Năm xuất bản (1000-2100)",
    )

    description: str | None = Field(default=None, max_length=1000)

    # Bài 93: gt=0 → author_id phải > 0 (không cho phép 0 hay âm)
    author_id: int = Field(gt=0, description="ID của tác giả")
    category_id: int = Field(gt=0, description="ID của danh mục")

    # Bài 94: @field_validator
    # Validate logic không làm được bằng Field constraint.
    # title đã được normalize bởi NormalizedTitle (Bài 96),
    # validator này bắt thêm trường hợp edge case sau normalize.
    @field_validator("title", mode="after")
    @classmethod
    def title_must_have_content(cls, v: str) -> str:
        """Sau normalize, title vẫn phải có nội dung thực sự."""
        if not v.strip():
            raise ValueError("title không được rỗng sau khi chuẩn hoá")
        return v


class BookCreate(BookBase):
    """Schema tạo book mới — Bài 94 @model_validator, Bài 100 Best Practice.

    Bài 100 Best Practice:
        BookCreate  → input từ user, validate chặt
        BookUpdate  → partial update, tất cả optional
        Book        → response trả về client, thêm computed fields
    """

    # Bài 94: @model_validator — validate NHIỀU fields cùng lúc (cross-field)
    # mode="after" → chạy SAU khi tất cả fields đã được parse và validate riêng lẻ
    # Nhận `self` thay vì `cls` — truy cập được tất cả fields
    @model_validator(mode="after")
    def author_and_category_must_differ(self) -> "BookCreate":
        """author_id và category_id không được trùng nhau.

        Đây là ví dụ cross-field validation — không thể làm với @field_validator
        vì mỗi @field_validator chỉ nhìn thấy 1 field tại 1 thời điểm.
        """
        if self.author_id == self.category_id:
            raise ValueError(
                f"author_id ({self.author_id}) và category_id ({self.category_id}) "
                "không được giống nhau"
            )
        return self

    # ── @classmethod — alternative constructors ───────────────────────────────
    # (Đây là Python OOP concept, không phải Pydantic — nhắc lại để dễ so sánh)
    # @classmethod nhận cls thay vì self → tạo instance theo cách khác ngoài __init__

    @classmethod
    def from_csv_row(cls, row: dict) -> "BookCreate":
        """Tạo BookCreate từ 1 dòng CSV đã parse thành dict.

        Dùng khi import hàng loạt từ file CSV:
            reader = csv.DictReader(file)
            for row in reader:
                book_in = BookCreate.from_csv_row(row)

        cls = BookCreate → cls(...) tương đương BookCreate(...)
        """
        return cls(
            title=row["title"].strip(),
            description=row.get("description") or None,
            published_year=int(row["year"]) if row.get("year") else None,
            author_id=int(row["author_id"]),
            category_id=int(row["category_id"]),
        )

    @classmethod
    def from_form(cls, form_data: dict) -> "BookCreate":
        """Tạo BookCreate từ HTML form data (keys có thể khác tên field)."""
        return cls(
            title=form_data["book_title"],
            description=form_data.get("book_description"),
            published_year=int(form_data["book_year"]) if form_data.get("book_year") else None,
            author_id=int(form_data["author"]),
            category_id=int(form_data["category"]),
        )


class BookUpdate(AppModel):
    """Schema cập nhật book — Bài 101 model_dump(exclude_unset=True).

    Tất cả fields optional — client chỉ gửi field muốn thay đổi.

    Bài 101 — model_dump:
        update = BookUpdate(title="Tên mới")

        update.model_dump()
        # {"title": "Tên mới", "published_year": None, "description": None, ...}
        # → TẤT CẢ fields, kể cả field không được gửi (giá trị None)

        update.model_dump(exclude_unset=True)
        # {"title": "Tên mới"}
        # → CHỈ fields đã được gửi, dùng cho PATCH để không ghi đè field khác
    """
    title: NormalizedTitle | None = Field(default=None, min_length=1, max_length=255)
    published_year: int | None = Field(default=None, ge=1000, le=2100)
    description: str | None = Field(default=None, max_length=1000)
    author_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)


class Book(BookBase):
    """Schema response trả về client — Bài 95 @computed_field, Bài 97 Nested Models.

    Bài 97: Nested Models
        author: Author   → không chỉ trả author_id=1,
                           trả về cả object {"id":1, "name":"Robert Martin"}
        category: Category → tương tự

    Bài 101: model_dump
        book.model_dump()
        # {
        #   "id": 1, "title": "Clean Code",
        #   "author": {"id": 1, "name": "Robert Martin"},    ← nested dict
        #   "category": {"id": 1, "name": "Programming"},    ← nested dict
        #   "age": 17,           ← computed field
        #   "display_name": "Clean Code (2008)",  ← computed field
        # }

        book.model_dump_json()  ← serialize thẳng ra JSON string, nhanh hơn json.dumps
    """
    id: int

    # Bài 97: Nested Models
    # author: Author → Pydantic tự convert dict thành Author object khi cần
    # from_attributes=True (AppModel) → đọc được từ SQLAlchemy relationship
    author: Author
    category: Category

    # ── Bài 95: @computed_field ───────────────────────────────────────────────
    #
    # @computed_field → property tính toán từ fields khác,
    # TỰ ĐỘNG xuất hiện trong model_dump() và model_dump_json().
    # Khác @property thông thường: @property không có trong output serialization.
    #
    # Cần @property bên dưới @computed_field.

    @computed_field
    @property
    def age(self) -> int | None:
        """Số năm từ khi xuất bản đến 2025.

        published_year=2008 → age=17
        published_year=None → age=None
        """
        if self.published_year is None:
            return None
        return 2025 - self.published_year

    @computed_field
    @property
    def display_name(self) -> str:
        """Tên hiển thị đầy đủ kèm năm xuất bản.

        "Clean Code" + 2008 → "Clean Code (2008)"
        "Unknown Book" + None → "Unknown Book"
        """
        if self.published_year:
            return f"{self.title} ({self.published_year})"
        return self.title
