from pydantic import BaseModel, ConfigDict

from app.schemas.author import Author
from app.schemas.category import Category


class BookBase(BaseModel):
    title: str
    description: str | None = None
    published_year: int | None = None
    author_id: int
    category_id: int


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    published_year: int | None = None
    author_id: int | None = None
    category_id: int | None = None


class Book(BookBase):
    id: int
    author: Author
    category: Category
    model_config = ConfigDict(from_attributes=True)
