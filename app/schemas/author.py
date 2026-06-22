"""Schemas cho Author — minh hoạ bài 90→94.

Bài 90: Foundation — BaseModel, type annotations
Bài 91: Default Conversions — str_strip_whitespace (kế thừa từ AppModel)
Bài 92: Mixing pydantic + typing — str | None, list
Bài 93: Field constraints — min_length, max_length, description
Bài 94: Field & Model Validators — @field_validator
"""
from __future__ import annotations

from pydantic import Field, field_validator

from app.schemas.base import AppModel


# ── Bài 90: Foundation ────────────────────────────────────────────────────────
# BaseModel là class cha của Pydantic. Khai báo fields với type annotations.
# Pydantic đọc type annotations → tự validate khi tạo instance.
#
# Ở đây kế thừa AppModel thay vì BaseModel trực tiếp (Bài 100: Best Practice).


class AuthorBase(AppModel):
    # Bài 93: Field constraints
    # min_length=1  → không cho phép string rỗng ""
    # max_length=100 → giới hạn độ dài tối đa
    # description   → hiển thị trong Swagger UI (tự động từ FastAPI)
    name: str = Field(
        min_length=1,
        max_length=100,
        description="Tên tác giả, tối đa 100 ký tự",
    )

    # Bài 92: Mixing pydantic + typing
    # str | None = None  → field optional, mặc định None nếu không truyền
    # Tương đương Optional[str] = None trong Python < 3.10
    biography: str | None = Field(
        default=None,
        max_length=2000,
        description="Tiểu sử tác giả (không bắt buộc)",
    )

    # Bài 94: @field_validator
    # Validate logic phức tạp hơn Field constraint không làm được.
    # mode="before" → chạy TRƯỚC khi Pydantic parse/coerce kiểu dữ liệu.
    #                 Nhận raw value từ input (có thể là bất kỳ type nào).
    # mode="after"  → chạy SAU khi đã parse xong, nhận đúng kiểu đã khai báo.
    @field_validator("name", mode="before")
    @classmethod
    def name_must_not_be_whitespace(cls, v: str) -> str:
        """Bắt trường hợp name = "   " (toàn khoảng trắng).

        Field(min_length=1) không bắt được vì "   " có length=3.
        Cần validator riêng để strip rồi kiểm tra lại.
        """
        if isinstance(v, str) and not v.strip():
            raise ValueError("name không được chỉ có khoảng trắng")
        return v

    @field_validator("biography", mode="before")
    @classmethod
    def clean_biography(cls, v: str | None) -> str | None:
        """Convert biography rỗng thành None thay vì lưu string trắng."""
        if v is None:
            return None
        stripped = v.strip()
        # "" sau strip → None (không lưu string rỗng vào DB)
        return stripped if stripped else None


class AuthorCreate(AuthorBase):
    """Schema dùng khi tạo author mới (POST /authors).

    Bài 100 Best Practice: tách Create / Update / Response thành 3 class riêng.
    - Create  → validate input chặt, tất cả required fields bắt buộc
    - Update  → tất cả optional (PATCH)
    - Response → thêm id và các field tính toán
    """
    pass


class AuthorUpdate(AppModel):
    """Schema dùng khi cập nhật author (PUT /authors/{id}).

    Tất cả fields là Optional — client chỉ gửi field muốn thay đổi.
    Dùng model_dump(exclude_unset=True) để chỉ update field được gửi.

    Bài 101 — model_dump:
        update = AuthorUpdate(name="Tên mới")
        update.model_dump(exclude_unset=True)  → {"name": "Tên mới"}
        update.model_dump()                    → {"name": "Tên mới", "biography": None}
    """
    name: str | None = Field(default=None, min_length=1, max_length=100)
    biography: str | None = Field(default=None, max_length=2000)

    @field_validator("name", mode="before")
    @classmethod
    def name_must_not_be_whitespace(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v.strip():
            raise ValueError("name không được chỉ có khoảng trắng")
        return v


class Author(AuthorBase):
    """Schema response trả về client (GET /authors).

    Thêm id so với AuthorBase.
    from_attributes=True (kế thừa từ AppModel) → đọc được từ SQLAlchemy object.
    """
    id: int
