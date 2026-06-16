from sqlalchemy.orm import Session

from app.models.author import Author
from app.repositories.base import BaseRepository


class AuthorRepository(BaseRepository[Author]):
    """Repository cho Author — kế thừa toàn bộ CRUD từ BaseRepository.

    Inheritance — không cần viết lại get_by_id, list, create, update, delete.
    Chỉ thêm method đặc thù của Author.
    """

    def __init__(self, db: Session):
        # Gọi __init__ của class cha, truyền model=Author
        super().__init__(model=Author, db=db)

    def get_by_name(self, name: str) -> Author | None:
        """Method đặc thù — chỉ Author mới có, Base không có."""
        return self.db.query(Author).filter(Author.name == name).first()

    def exists_by_name(self, name: str) -> bool:
        return self.get_by_name(name) is not None
