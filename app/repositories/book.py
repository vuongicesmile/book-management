from sqlalchemy.orm import Session

from app.models.book import Book
from app.repositories.base import BaseRepository


class BookRepository(BaseRepository[Book]):
    """Repository cho Book — kế thừa CRUD từ BaseRepository."""

    def __init__(self, db: Session):
        super().__init__(model=Book, db=db)

    # ── @staticmethod ──────────────────────────────────────────────────────
    #
    # Dùng khi: logic thuộc về class về mặt ý nghĩa,
    #           nhưng không cần self (instance) hay cls (class).
    #           Chỉ xử lý input → output thuần túy.
    #
    # Gọi qua class:    BookRepository.normalize_title("  clean code  ")
    # Gọi qua instance: repo.normalize_title("  clean code  ")   (cả 2 đều được)

    @staticmethod
    def normalize_title(title: str) -> str:
        """Chuẩn hóa title — strip khoảng trắng, Title Case.

        "  clean code  " → "Clean Code"
        "the pragmatic programmer" → "The Pragmatic Programmer"

        @staticmethod vì:
        - Không cần self.db hay self.model
        - Không cần cls
        - Chỉ là string utility thuộc về domain Book
        """
        return title.strip().title()

    @staticmethod
    def is_valid_year(year: int | None) -> bool:
        """Validate published_year hợp lệ.

        Thêm @staticmethod thứ 2 để thấy pattern rõ hơn:
        - Không cần DB, không cần instance
        - Logic validation thuộc về Book domain
        """
        if year is None:
            return True
        return 1000 <= year <= 2100

    # ── Methods dùng @staticmethod bên trong ──────────────────────────────

    def create(self, **data) -> Book:
        """Override create — normalize title và validate year trước khi lưu."""
        if "title" in data:
            # Gọi staticmethod qua class name — rõ ràng hơn gọi qua self
            data["title"] = BookRepository.normalize_title(data["title"])
        if not BookRepository.is_valid_year(data.get("published_year")):
            raise ValueError(f"published_year không hợp lệ: {data['published_year']}")
        return super().create(**data)

    def get_by_title(self, title: str) -> Book | None:
        # normalize trước khi query — tránh miss do khoảng trắng hay case
        normalized = BookRepository.normalize_title(title)
        return self.db.query(Book).filter(Book.title == normalized).first()

    def exists_by_title(self, title: str) -> bool:
        return self.get_by_title(title) is not None

    def search(self, q: str) -> list[Book]:
        """List comprehension — lọc books khớp query."""
        books = self.db.query(Book).all()
        q_lower = q.lower()
        return [
            b for b in books
            if q_lower in b.title.lower()
            or (b.description and q_lower in b.description.lower())
        ]

    def stats(self) -> dict:
        """Set + dict comprehension — thống kê books."""
        books = self.db.query(Book).all()
        unique_years = {b.published_year for b in books if b.published_year}
        active_author_ids = {b.author_id for b in books}
        books_per_category = {
            cat_id: len([b for b in books if b.category_id == cat_id])
            for cat_id in {b.category_id for b in books}
        }
        return {
            "total_books": len(books),
            "unique_years": sorted(unique_years),
            "active_authors_count": len(active_author_ids),
            "books_per_category": books_per_category,
        }

    def iter_as_csv(self):
        """Generator — stream CSV từng dòng."""
        yield "id,title,author_id,category_id,published_year\n"
        for book in self.db.query(Book).yield_per(100):
            yield f"{book.id},{book.title},{book.author_id},{book.category_id},{book.published_year or ''}\n"

    # ── Embedding methods (Bài 108) ────────────────────────────────────────

    def save_embedding(self, book_id: int, embedding_json: str) -> Book:
        """Lưu embedding JSON vào column embedding của book."""
        book = self.get_by_id(book_id)
        book.embedding = embedding_json
        self.db.commit()
        self.db.refresh(book)
        return book

    def get_books_with_embedding(self) -> list[Book]:
        """Lấy tất cả books đã có embedding — dùng cho semantic search."""
        return self.db.query(Book).filter(Book.embedding.isnot(None)).all()

    def update_description(self, book_id: int, description: str) -> Book:
        """Cập nhật description của book (dùng sau khi AI generate)."""
        book = self.get_by_id(book_id)
        book.description = description
        self.db.commit()
        self.db.refresh(book)
        return book
