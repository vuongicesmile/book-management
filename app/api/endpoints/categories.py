from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.models import Category
from app.schemas.category import CategoryCreate, CategoryUpdate, Category as CategorySchema
from app.api.deps import get_db, get_or_404, save_to_db
from sqlalchemy.orm import Session

router = APIRouter()

@router.get("/", response_model=List[CategorySchema])
def list_categories(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
    ):
    """
    Endpoint để lấy danh sách tất cả categories, hỗ trợ phân trang với skip và limit.
    thường ko chia như vầy, thường chia services với responsitory, nhưng ở đây để đơn giản nên viết thẳng trong endpoint luôn. Nếu có nhiều logic phức tạp hơn thì nên tách ra services để dễ bảo trì và test hơn.
    """

    categories = db.query(Category).offset(skip).limit(limit).all()
    return categories


@router.get("/{category_id}", response_model=CategorySchema)
def get_category(category_id: int, db: Session = Depends(get_db)):
    """
    Endpoint để lấy thông tin chi tiết của một category dựa trên ID.
    Nếu category không tồn tại, trả về lỗi 404.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category    


@router.post("/", response_model=CategorySchema, status_code=status.HTTP_201_CREATED) 
def create_category(category_in: CategoryCreate, db: Session = Depends(get_db)):
    """
    Endpoint để tạo mới một category. Nhận dữ liệu từ client thông qua schema CategoryCreate.
    Trả về category vừa được tạo với status code 201.
    """
    exxisting_category = db.query(Category).filter(Category.name == category_in.name).first()
    if exxisting_category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category with this name already exists")
    category = Category(name=category_in.name, description=category_in.description)
    db.add(category)
    db.commit()
    db.refresh(category)  # Làm mới instance để lấy ID đã được gán sau khi commit
    return category  

@router.put("/{category_id}", response_model=CategorySchema)
def update_category(category_id: int, category_in: CategoryUpdate, db: Session = Depends(get_db)):
    """
    Endpoint để cập nhật thông tin của một category dựa trên ID. Nhận dữ liệu cập nhật từ client thông qua schema CategoryUpdate.
    Nếu category không tồn tại, trả về lỗi 404.
    Trả về category đã được cập nhật.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    
    # exclude_unset=True — chỉ lấy fields client gửi lên, bỏ qua fields không gửi
    # thay vì if thủ công từng field:
    #   if category_in.name is not None: category.name = category_in.name
    #   if category_in.description is not None: category.description = category_in.description
    for field, value in category_in.model_dump(exclude_unset=True).items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)
    return category

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    """
    Endpoint để xóa một category dựa trên ID. Nếu category không tồn tại, trả về lỗi 404.
    Trả về status code 204 No Content nếu xóa thành công.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    
    db.delete(category)
    db.commit()
    return None  # FastAPI sẽ tự động trả về response với status code 204 khi trả về None     