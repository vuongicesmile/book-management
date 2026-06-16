from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from sqlalchemy.orm import Session

from app.api.deps import get_db, get_or_404, save_to_db
from app.models import Author, Book, Category
from app.schemas.book import BookCreate, BookUpdate, Book as BookSchema

router = APIRouter()


@router.get("/", response_model=List[BookSchema])
def list_books(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Lấy danh sách tất cả books, hỗ trợ phân trang."""
    return db.query(Book).offset(skip).limit(limit).all()


@router.get("/search", response_model=List[BookSchema])
def search_books(q: str, db: Session = Depends(get_db)):
    """Tìm kiếm books theo title hoặc description.

    List comprehension — lọc kết quả từ DB theo query string.
    Thay vì viết vòng for + if thủ công:
        results = []
        for book in books:
            if q in book.title:
                results.append(book)

    List comprehension viết gọn hơn và trả về list trực tiếp.
    """
    books = db.query(Book).all()
    q_lower = q.lower()
    return [
        b for b in books
        if q_lower in b.title.lower()
        or (b.description and q_lower in b.description.lower())
    ]


@router.get("/stats")
def book_stats(db: Session = Depends(get_db)):
    """Thống kê tổng quan books.

    Set comprehension — lấy unique values, tự động loại trùng:
        {b.published_year for b in books}  → {2020, 2021, 2023} không có duplicate

    Dict comprehension — xây dict từ iterable:
        {key: value for item in iterable}
        → {"Fiction": 5, "Science": 3, ...}
    """
    books = db.query(Book).all()

    # set comprehension — unique published years, bỏ None
    unique_years = {b.published_year for b in books if b.published_year}

    # set comprehension — unique author ids đang có sách
    active_author_ids = {b.author_id for b in books}

    # dict comprehension — đếm số sách theo category_id
    books_per_category = {
        cat_id: len([b for b in books if b.category_id == cat_id])
        for cat_id in {b.category_id for b in books}  # set làm key để không bị trùng
    }

    return {
        "total_books": len(books),
        "unique_years": sorted(unique_years),
        "active_authors_count": len(active_author_ids),
        "books_per_category": books_per_category,
    }


def _iter_book_titles(db: Session):
    """Generator — yield từng title thay vì load hết vào RAM.

    Bình thường:  titles = [b.title for b in db.query(Book).all()]
                  → load toàn bộ 100.000 books vào RAM cùng lúc

    Generator:    yield b.title từng cái một
                  → chỉ dùng RAM cho 1 book tại 1 thời điểm
                  → yield_per(100) = fetch 100 rows/lần từ DB, không phải tất cả

    Hữu ích khi dataset lớn hoặc stream response.
    """
    for book in db.query(Book).yield_per(100):
        yield book.title


@router.get("/export/titles")
def export_titles(db: Session = Depends(get_db)):
    """Export danh sách titles dùng generator để tiết kiệm RAM."""
    # generator expression — lazy evaluation, chỉ tính khi cần
    titles = list(_iter_book_titles(db))
    return {"total": len(titles), "titles": titles}


@router.get("/{book_id}", response_model=BookSchema)
def get_book(book_id: int, db: Session = Depends(get_db)):
    """Lấy thông tin chi tiết của một book. Trả về 404 nếu không tồn tại."""
    return get_or_404(db, Book, id=book_id)


@router.post("/", response_model=BookSchema, status_code=status.HTTP_201_CREATED)
def create_book(book_in: BookCreate, db: Session = Depends(get_db)):
    """Tạo mới một book. Trả về 400 nếu title đã tồn tại hoặc author/category không hợp lệ."""
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
    """Cập nhật thông tin một book. Trả về 404 nếu không tồn tại."""
    book = get_or_404(db, Book, id=book_id)
    for field, value in book_in.model_dump(exclude_unset=True).items():
        setattr(book, field, value)
    db.commit()
    db.refresh(book)
    return book


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int, db: Session = Depends(get_db)):
    """Xóa một book. Trả về 404 nếu không tồn tại."""
    book = get_or_404(db, Book, id=book_id)
    db.delete(book)
    db.commit()
    return None
