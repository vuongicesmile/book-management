from pydantic import BaseModel, ConfigDict


class AuthorBase(BaseModel):
    name: str
    biography: str | None = None


class AuthorCreate(AuthorBase):
    pass


class AuthorUpdate(BaseModel):
    name: str | None = None
    biography: str | None = None


class AuthorInDBBase(AuthorBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class Author(AuthorInDBBase):
    pass
