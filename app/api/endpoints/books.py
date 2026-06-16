from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from typing import List

from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.decorators import log_duration, validate_pagination
from app.repositories import AuthorRepository, BookRepository, CategoryRepository
from app.schemas.book import BookCreate, BookUpdate, Book as BookSchema

router = APIRouter()


@router.get("/", response_model=List[BookSchema])
@log_duration
@validate_pagination()
def list_books(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Lấy danh sách tất cả books, hỗ trợ phân trang."""
    # Trước: db.query(Book).offset(skip).limit(limit).all()
    # Sau:   BookRepository(db).list(skip, limit)
    return BookRepository(db).list(skip, limit)


@router.get("/search", response_model=List[BookSchema])
@log_duration
def search_books(q: str, db: Session = Depends(get_db)):
    """Tìm kiếm books theo title hoặc description."""
    return BookRepository(db).search(q)


@router.get("/stats")
@log_duration
def book_stats(db: Session = Depends(get_db)):
    """Thống kê tổng quan books."""
    return BookRepository(db).stats()


@router.get("/export/titles")
@log_duration
def export_titles(db: Session = Depends(get_db)):
    """Export danh sách titles."""
    repo = BookRepository(db)
    titles = [title for title in repo.iter_as_csv() if not title.startswith("id,")]
    return {"total": len(titles), "titles": [t.split(",")[1] for t in titles]}


@router.get("/export/csv")
def export_csv(db: Session = Depends(get_db)):
    """Stream CSV response dùng generator."""
    return StreamingResponse(
        BookRepository(db).iter_as_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=books.csv"},
    )


@router.get("/{book_id}", response_model=BookSchema)
def get_book(book_id: int, db: Session = Depends(get_db)):
    return BookRepository(db).get_by_id(book_id)


@router.post("/", response_model=BookSchema, status_code=status.HTTP_201_CREATED)
def create_book(book_in: BookCreate, db: Session = Depends(get_db)):
    repo = BookRepository(db)
    if repo.exists_by_title(book_in.title):
        raise HTTPException(status_code=400, detail="Book with this title already exists")
    # validate author và category tồn tại
    AuthorRepository(db).get_by_id(book_in.author_id)
    CategoryRepository(db).get_by_id(book_in.category_id)
    return repo.create(**book_in.model_dump())


@router.put("/{book_id}", response_model=BookSchema)
def update_book(book_id: int, book_in: BookUpdate, db: Session = Depends(get_db)):
    return BookRepository(db).update(book_id, **book_in.model_dump(exclude_unset=True))


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int, db: Session = Depends(get_db)):
    BookRepository(db).delete(book_id)
