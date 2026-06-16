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


@router.get("/{book_id}", response_model=BookSchema)
def get_book(book_id: int, db: Session = Depends(get_db)):
    """Lấy thông tin chi tiết của một book. Trả về 404 nếu không tồn tại."""
    # **kwargs: truyền id=book_id → filter_by(id=book_id)
    return get_or_404(db, Book, id=book_id)


@router.post("/", response_model=BookSchema, status_code=status.HTTP_201_CREATED)
def create_book(book_in: BookCreate, db: Session = Depends(get_db)):
    """Tạo mới một book. Trả về 400 nếu title đã tồn tại hoặc author/category không hợp lệ."""
    if db.query(Book).filter(Book.title == book_in.title).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Book with this title already exists",
        )
    # get_or_404 dùng **kwargs để validate author và category tồn tại
    # nếu không tìm thấy → raise 404 tự động, không cần if/raise thủ công
    get_or_404(db, Author, id=book_in.author_id)
    get_or_404(db, Category, id=book_in.category_id)

    # **kwargs: unpack toàn bộ fields từ Pydantic schema vào model
    # book_in.model_dump() → {"title": "...", "author_id": 1, "category_id": 2, ...}
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
