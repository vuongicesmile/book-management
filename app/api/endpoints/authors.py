from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories import AuthorRepository
from app.schemas.author import AuthorCreate, AuthorUpdate, Author as AuthorSchema

router = APIRouter()


@router.get("/", response_model=List[AuthorSchema])
def list_authors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return AuthorRepository(db).list(skip, limit)


@router.get("/{author_id}", response_model=AuthorSchema)
def get_author(author_id: int, db: Session = Depends(get_db)):
    return AuthorRepository(db).get_by_id(author_id)


@router.post("/", response_model=AuthorSchema, status_code=status.HTTP_201_CREATED)
def create_author(author_in: AuthorCreate, db: Session = Depends(get_db)):
    repo = AuthorRepository(db)
    if repo.exists_by_name(author_in.name):
        raise HTTPException(status_code=400, detail="Author with this name already exists")
    return repo.create(**author_in.model_dump())


@router.put("/{author_id}", response_model=AuthorSchema)
def update_author(author_id: int, author_in: AuthorUpdate, db: Session = Depends(get_db)):
    return AuthorRepository(db).update(author_id, **author_in.model_dump(exclude_unset=True))


@router.delete("/{author_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_author(author_id: int, db: Session = Depends(get_db)):
    AuthorRepository(db).delete(author_id)
