from collections.abc import Generator
from typing import Type, TypeVar

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import SessionLocal

# TypeVar("T") — biến kiểu generic, placeholder cho "bất kỳ class nào"
# Mục đích: giúp type checker hiểu return type khớp với model truyền vào
#
# Không có TypeVar:
#   def get_or_404(db, model, **filters) -> ???    # type checker không biết trả về gì
#
# Có TypeVar:
#   def get_or_404(db, model: Type[T], **filters) -> T
#   get_or_404(db, Book, id=1)    → type checker biết return là Book
#   get_or_404(db, Author, id=1)  → type checker biết return là Author
#
# Tóm tắt: T = "kiểu nào truyền vào thì trả ra kiểu đó" — giống generic<T> trong Java/TypeScript
T = TypeVar("T")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_or_404(db: Session, model: Type[T], **filters) -> T:
    """Tìm record theo filters, raise 404 nếu không tìm thấy.

    Dùng **kwargs để nhận bất kỳ filter nào:
        get_or_404(db, Book, id=1)
        get_or_404(db, Author, name="Vuong")

    **filters được SQLAlchemy dịch thành WHERE clause:
        filter_by(id=1)      → WHERE id = 1
        filter_by(name="X")  → WHERE name = 'X'
    """
    obj = db.query(model).filter_by(**filters).first()
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{model.__name__} not found",
        )
    return obj  # type: ignore[return-value]


def save_to_db(db: Session, model: Type[T], **data) -> T:
    """Tạo và lưu 1 record mới vào DB.

    Dùng **kwargs để nhận bất kỳ field nào của model:
        save_to_db(db, Author, name="Vuong", biography="...")
        save_to_db(db, Book, **book_in.model_dump())

    **data được unpack thành keyword args khi tạo model:
        model(**data) == Author(name="Vuong", biography="...")
    """
    obj = model(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj  # type: ignore[return-value]
