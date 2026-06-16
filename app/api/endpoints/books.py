import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from typing import List

from sqlalchemy.orm import Session

from app.api.deps import get_db, get_or_404, save_to_db
from app.core.decorators import log_duration, validate_pagination
from app.models import Author, Book, Category
from app.schemas.book import BookCreate, BookUpdate, Book as BookSchema

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=List[BookSchema])
@log_duration           # decorator 1 — log thời gian chạy
@validate_pagination()  # decorator 2 — validate skip/limit
def list_books(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Lấy danh sách tất cả books, hỗ trợ phân trang.

    Thứ tự decorator: từ dưới lên trên khi wrap, từ trên xuống khi chạy.
        @log_duration
        @validate_pagination()
        def list_books(...)

        # Python dịch thành:
        list_books = log_duration(validate_pagination()(list_books))
        # Khi gọi:
        #   1. log_duration.wrapper chạy → bắt đầu đếm giờ
        #   2. validate_pagination.wrapper chạy → check limit/skip
        #   3. list_books gốc chạy → query DB
        #   2. validate_pagination.wrapper trả kết quả
        #   1. log_duration.wrapper log duration → trả kết quả
    """
    return db.query(Book).offset(skip).limit(limit).all()


@router.get("/search", response_model=List[BookSchema])
@log_duration
def search_books(q: str, db: Session = Depends(get_db)):
    """Tìm kiếm books theo title hoặc description.

    List comprehension — lọc kết quả từ DB theo query string.
    """
    books = db.query(Book).all()
    q_lower = q.lower()
    return [
        b for b in books
        if q_lower in b.title.lower()
        or (b.description and q_lower in b.description.lower())
    ]


@router.get("/stats")
@log_duration
def book_stats(db: Session = Depends(get_db)):
    """Thống kê tổng quan books.

    Set comprehension — unique values, tự động loại trùng.
    Dict comprehension — xây dict từ iterable.
    """
    books = db.query(Book).all()

    # set comprehension — unique published years, bỏ None
    unique_years = {b.published_year for b in books if b.published_year}

    # set comprehension — unique author ids đang có sách
    active_author_ids = {b.author_id for b in books}

    # dict comprehension — đếm số sách theo category_id
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


# ── Generator endpoints ────────────────────────────────────────────────────

def _iter_book_titles(db: Session):
    """Generator — yield từng title, không load hết vào RAM.

    yield_per(100): fetch 100 rows/lần từ DB thay vì toàn bộ.
    """
    for book in db.query(Book).yield_per(100):
        yield book.title


def _iter_books_as_csv(db: Session):
    """Generator — stream CSV từng dòng.

    Thay vì build toàn bộ string rồi trả:
        content = "id,title,...\\n"
        for book in books:
            content += f"{book.id},..."   # RAM tăng dần

    Generator yield từng dòng — RAM gần như không tăng dù có triệu books.
    """
    yield "id,title,author_id,category_id,published_year\n"
    for book in db.query(Book).yield_per(100):
        yield f"{book.id},{book.title},{book.author_id},{book.category_id},{book.published_year or ''}\n"


@router.get("/export/titles")
@log_duration
def export_titles(db: Session = Depends(get_db)):
    """Export danh sách titles dùng generator."""
    titles = list(_iter_book_titles(db))
    return {"total": len(titles), "titles": titles}


@router.get("/export/csv")
def export_csv(db: Session = Depends(get_db)):
    """Stream CSV response dùng generator — không buffer toàn bộ trong RAM.

    StreamingResponse nhận generator, gửi từng chunk xuống client ngay khi có.
    Client nhận được dữ liệu trước khi server xử lý xong toàn bộ.
    """
    return StreamingResponse(
        _iter_books_as_csv(db),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=books.csv"},
    )


# ── CRUD endpoints ─────────────────────────────────────────────────────────

@router.get("/{book_id}", response_model=BookSchema)
def get_book(book_id: int, db: Session = Depends(get_db)):
    """Lấy thông tin chi tiết của một book. Trả về 404 nếu không tồn tại."""
    return get_or_404(db, Book, id=book_id)


@router.post("/", response_model=BookSchema, status_code=status.HTTP_201_CREATED)
def create_book(book_in: BookCreate, db: Session = Depends(get_db)):
    """Tạo mới một book."""
    if db.query(Book).filter(Book.title == book_in.title).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Book with this title already exists",
        )
    get_or_404(db, Author, id=book_in.author_id)
    get_or_404(db, Category, id=book_in.category_id)
    return save_to_db(db, Book, **book_in.model_dump())


@router.put("/{book_id}", response_model=BookSchema)
def update_book(book_id: int, book_in: BookUpdate, db: Session = Depends(get_db)):
    """Cập nhật thông tin một book."""
    book = get_or_404(db, Book, id=book_id)
    for field, value in book_in.model_dump(exclude_unset=True).items():
        setattr(book, field, value)
    db.commit()
    db.refresh(book)
    return book


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int, db: Session = Depends(get_db)):
    """Xóa một book."""
    book = get_or_404(db, Book, id=book_id)
    db.delete(book)
    db.commit()
    return None
