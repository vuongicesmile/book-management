from pydantic import BaseModel, ConfigDict

from app.schemas.author import Author
from app.schemas.category import Category


class BookBase(BaseModel):
    title: str
    description: str | None = None
    published_year: int | None = None
    author_id: int
    category_id: int


class BookCreate(BookBase):
    # ── @classmethod ───────────────────────────────────────────────────────
    #
    # Dùng khi: muốn tạo instance theo cách khác ngoài __init__ thông thường.
    # cls = chính class này (BookCreate), không phải instance.
    #
    # Gọi qua class:  BookCreate.from_csv_row(row)
    #                 BookCreate.from_form(form_data)
    # KHÔNG gọi qua instance: book.from_csv_row(...)  ← sai về ý nghĩa
    #
    # So sánh:
    #   __init__      → BookCreate(title="...", author_id=1, ...)  — cách thường
    #   @classmethod  → BookCreate.from_csv_row(row)               — alternative constructor

    @classmethod
    def from_csv_row(cls, row: dict) -> "BookCreate":
        """Tạo BookCreate từ 1 dòng CSV đã parse thành dict.

        Dùng khi import hàng loạt từ file CSV:
            reader = csv.DictReader(file)
            for row in reader:
                book_in = BookCreate.from_csv_row(row)

        cls = BookCreate → cls(...) tương đương BookCreate(...)
        Nếu sau này có class con kế thừa BookCreate,
        cls sẽ là class con đó — không hardcode tên class.
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
        """Tạo BookCreate từ HTML form data (keys có thể khác tên field).

        Dùng khi nhận data từ form HTML truyền thống:
            form_data = {
                "book_title": "Clean Code",
                "book_year": "2008",
                "author": "1",
                "category": "2",
            }
        """
        return cls(
            title=form_data["book_title"],
            description=form_data.get("book_description"),
            published_year=int(form_data["book_year"]) if form_data.get("book_year") else None,
            author_id=int(form_data["author"]),
            category_id=int(form_data["category"]),
        )


class BookUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    published_year: int | None = None
    author_id: int | None = None
    category_id: int | None = None


class Book(BookBase):
    id: int
    author: Author
    category: Category
    model_config = ConfigDict(from_attributes=True)
