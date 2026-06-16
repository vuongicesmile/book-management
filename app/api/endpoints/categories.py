from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate, Category as CategorySchema

router = APIRouter()


@router.get("/", response_model=List[CategorySchema])
def list_categories(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return CategoryRepository(db).list(skip, limit)


@router.get("/{category_id}", response_model=CategorySchema)
def get_category(category_id: int, db: Session = Depends(get_db)):
    return CategoryRepository(db).get_by_id(category_id)


@router.post("/", response_model=CategorySchema, status_code=status.HTTP_201_CREATED)
def create_category(category_in: CategoryCreate, db: Session = Depends(get_db)):
    repo = CategoryRepository(db)
    if repo.exists_by_name(category_in.name):
        raise HTTPException(status_code=400, detail="Category with this name already exists")
    return repo.create(**category_in.model_dump())


@router.put("/{category_id}", response_model=CategorySchema)
def update_category(category_id: int, category_in: CategoryUpdate, db: Session = Depends(get_db)):
    return CategoryRepository(db).update(category_id, **category_in.model_dump(exclude_unset=True))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    CategoryRepository(db).delete(category_id)
