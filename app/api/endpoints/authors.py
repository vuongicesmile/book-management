from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Author
from app.schemas.author import AuthorCreate, AuthorUpdate, Author as AuthorSchema

router = APIRouter()


@router.get("/", response_model=List[AuthorSchema])
def list_authors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Lấy danh sách tất cả authors, hỗ trợ phân trang."""
    return db.query(Author).offset(skip).limit(limit).all()


@router.get("/{author_id}", response_model=AuthorSchema)
def get_author(author_id: int, db: Session = Depends(get_db)):
    """Lấy thông tin chi tiết của một author. Trả về 404 nếu không tồn tại."""
    author = db.query(Author).filter(Author.id == author_id).first()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    return author


@router.post("/", response_model=AuthorSchema, status_code=status.HTTP_201_CREATED)
def create_author(author_in: AuthorCreate, db: Session = Depends(get_db)):
    """Tạo mới một author. Trả về 400 nếu tên đã tồn tại."""
    existing = db.query(Author).filter(Author.name == author_in.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Author with this name already exists")
    author = Author(name=author_in.name, biography=author_in.biography)
    db.add(author)
    db.commit()
    db.refresh(author)
    return author


@router.put("/{author_id}", response_model=AuthorSchema)
def update_author(author_id: int, author_in: AuthorUpdate, db: Session = Depends(get_db)):
    """Cập nhật thông tin một author. Trả về 404 nếu không tồn tại."""
    author = db.query(Author).filter(Author.id == author_id).first()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    if author_in.name is not None:
        author.name = author_in.name
    if author_in.biography is not None:
        author.biography = author_in.biography
    db.commit()
    db.refresh(author)
    return author


@router.delete("/{author_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_author(author_id: int, db: Session = Depends(get_db)):
    """Xóa một author. Trả về 404 nếu không tồn tại."""
    author = db.query(Author).filter(Author.id == author_id).first()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    db.delete(author)
    db.commit()
    return None
