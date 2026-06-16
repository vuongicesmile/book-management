from sqlalchemy.orm import Session

from app.models.book import Book
from app.repositories.base import BaseRepository


class BookRepository(BaseRepository[Book]):
    """Repository cho Book — kế thừa CRUD từ BaseRepository.

    Thêm các method đặc thù: search, exists_by_title.
    """

    def __init__(self, db: Session):
        super().__init__(model=Book, db=db)

    def get_by_title(self, title: str) -> Book | None:
        return self.db.query(Book).filter(Book.title == title).first()

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
