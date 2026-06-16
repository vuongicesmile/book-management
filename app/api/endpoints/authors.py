from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from sqlalchemy.orm import Session

from app.api.deps import get_db, get_or_404, save_to_db
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
    # **kwargs: truyền id=author_id vào get_or_404 → filter_by(id=author_id)
    return get_or_404(db, Author, id=author_id)


@router.post("/", response_model=AuthorSchema, status_code=status.HTTP_201_CREATED)
def create_author(author_in: AuthorCreate, db: Session = Depends(get_db)):
    """Tạo mới một author. Trả về 400 nếu tên đã tồn tại."""
    if db.query(Author).filter(Author.name == author_in.name).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Author with this name already exists",
        )
    # **kwargs: author_in.model_dump() → {"name": "Vuong", "biography": "..."}
    # **{...} unpack thành: save_to_db(db, Author, name="Vuong", biography="...")
    # Trước đây: Author(name=author_in.name, biography=author_in.biography) — manual từng field
    # Bây giờ:   save_to_db(db, Author, **author_in.model_dump())  — tự động, thêm field mới không cần sửa
    return save_to_db(db, Author, **author_in.model_dump())


@router.put("/{author_id}", response_model=AuthorSchema)
def update_author(author_id: int, author_in: AuthorUpdate, db: Session = Depends(get_db)):
    """Cập nhật thông tin một author. Trả về 404 nếu không tồn tại."""
    author = get_or_404(db, Author, id=author_id)
    for field, value in author_in.model_dump(exclude_unset=True).items():
        setattr(author, field, value)
    db.commit()
    db.refresh(author)
    return author


@router.delete("/{author_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_author(author_id: int, db: Session = Depends(get_db)):
    """Xóa một author. Trả về 404 nếu không tồn tại."""
    author = get_or_404(db, Author, id=author_id)
    db.delete(author)
    db.commit()
    return None
