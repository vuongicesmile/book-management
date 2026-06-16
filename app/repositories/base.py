from typing import Type, TypeVar, Generic

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import Base

# Generic[T] — class cha dùng type parameter T
# Giống TypeScript: class Repository<T> { ... }
# T sẽ được xác định khi class con kế thừa:
#   class BookRepository(BaseRepository[Book]) → T = Book
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Class cha chứa CRUD chung cho tất cả models.

    OOP concepts áp dụng ở đây:
    - Generic[T]     : type parameter, giữ type safety khi kế thừa
    - __init__       : constructor, nhận model class và db session
    - Encapsulation  : self.model, self.db là private state của instance
    - Inheritance    : BookRepository(BaseRepository[Book]) kế thừa hết methods này
    """

    def __init__(self, model: Type[ModelType], db: Session):
        # Encapsulation — gom state vào instance, không để biến rời rạc
        self.model = model
        self.db = db

    def get_by_id(self, id: int) -> ModelType:
        obj = self.db.query(self.model).filter(self.model.id == id).first()
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__} not found",
            )
        return obj

    def list(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        return self.db.query(self.model).offset(skip).limit(limit).all()

    def create(self, **data) -> ModelType:
        # **kwargs — nhận bất kỳ fields nào, unpack vào constructor
        obj = self.model(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, id: int, **data) -> ModelType:
        obj = self.get_by_id(id)
        for field, value in data.items():
            setattr(obj, field, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, id: int) -> None:
        obj = self.get_by_id(id)
        self.db.delete(obj)
        self.db.commit()
