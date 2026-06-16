from sqlalchemy.orm import Session

from app.models.category import Category
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    """Repository cho Category — kế thừa CRUD từ BaseRepository."""

    def __init__(self, db: Session):
        super().__init__(model=Category, db=db)

    def get_by_name(self, name: str) -> Category | None:
        return self.db.query(Category).filter(Category.name == name).first()

    def exists_by_name(self, name: str) -> bool:
        return self.get_by_name(name) is not None
