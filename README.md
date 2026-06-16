# Book Management API

REST API quản lý sách đơn giản, xây dựng bằng FastAPI + SQLAlchemy + SQLite.

---

## Mục lục

1. [Công nghệ sử dụng](#1-công-nghệ-sử-dụng)
2. [Cấu trúc thư mục](#2-cấu-trúc-thư-mục)
3. [Cài đặt môi trường](#3-cài-đặt-môi-trường)
4. [Cấu trúc code từng phần](#4-cấu-trúc-code-từng-phần)
   - [4.1 Config](#41-config--appcoreconfpy)
   - [4.2 Database Base](#42-database-base--appdbbasepy)
   - [4.3 Database Session](#43-database-session--appdbsessionpy)
   - [4.4 Models](#44-models--appmodels)
   - [4.5 Schemas](#45-schemas--appschemas)
   - [4.6 Dependencies](#46-dependencies--appapidepspy)
   - [4.7 Endpoints](#47-endpoints--appapiendpoints)
   - [4.8 Main App](#48-main-app--appmainpy)
5. [Database Migration với Alembic](#5-database-migration-với-alembic)
6. [Chạy server](#6-chạy-server)
7. [API Reference](#7-api-reference)

---

## 1. Công nghệ sử dụng

| Package | Phiên bản | Mục đích |
|---|---|---|
| `fastapi[standard]` | ≥0.100 | Web framework, tự động tạo Swagger docs |
| `sqlalchemy` | ≥2.0 | ORM — làm việc với database bằng Python |
| `alembic` | ≥1.12 | Quản lý migration schema database |
| `pydantic` | v2 | Validate và serialize dữ liệu |
| `python-multipart` | - | Hỗ trợ upload file qua form |

---

## 2. Cấu trúc thư mục

```
book-management/
├── app/
│   ├── api/
│   │   ├── deps.py              # Dependency injection (get_db)
│   │   └── endpoints/
│   │       ├── authors.py       # CRUD endpoints cho Author
│   │       ├── books.py         # CRUD endpoints cho Book
│   │       └── categories.py    # CRUD endpoints cho Category
│   ├── core/
│   │   └── config.py            # Cấu hình ứng dụng (Settings)
│   ├── db/
│   │   ├── base.py              # Khai báo Base class cho ORM
│   │   └── session.py           # Tạo engine và SessionLocal
│   ├── models/
│   │   ├── author.py            # SQLAlchemy model bảng authors
│   │   ├── book.py              # SQLAlchemy model bảng books
│   │   └── category.py          # SQLAlchemy model bảng categories
│   ├── schemas/
│   │   ├── author.py            # Pydantic schemas cho Author
│   │   ├── book.py              # Pydantic schemas cho Book
│   │   └── category.py          # Pydantic schemas cho Category
│   └── main.py                  # Entry point, khởi tạo FastAPI app
├── migrations/
│   ├── env.py                   # Cấu hình Alembic
│   └── versions/                # Các file migration
├── alembic.ini                  # Cấu hình Alembic CLI
└── app.db                       # SQLite database file
```

---

## 3. Cài đặt môi trường

```bash
# 1. Cài gói venv (chỉ cần làm 1 lần trên Ubuntu/Debian)
sudo apt install python3.10-venv -y

# 2. Tạo virtual environment trong thư mục project
python3 -m venv .venv

# 3. Kích hoạt virtual environment
source .venv/bin/activate
# Dấu hiệu thành công: (.venv) xuất hiện ở đầu dòng terminal

# 4. Cài dependencies
pip install "fastapi[standard]" sqlalchemy alembic python-multipart

# 5. Khởi tạo Alembic (chỉ làm 1 lần)
alembic init migrations

# 6. Tạo migration lần đầu
alembic revision --autogenerate -m "Init tables"

# 7. Áp dụng migration vào database
alembic upgrade head

# 8. Chạy server
fastapi dev app/main.py
```

> **Lưu ý:** Mỗi lần mở terminal mới phải chạy lại `source .venv/bin/activate` để kích hoạt venv.

---

## 4. Cấu trúc code từng phần

### 4.1 Config — `app/core/config.py`

```python
from pydantic import BaseModel

class Settings(BaseModel):
    PROJECT_NAME: str = "Book management API"
    SQLALCHEMY_DATABASE_URL: str = "sqlite:///./app.db"

settings = Settings()
```

- `Settings` dùng Pydantic để khai báo cấu hình có kiểu dữ liệu rõ ràng.
- `settings` là một instance dùng chung toàn app — import từ bất kỳ đâu đều trỏ về cùng object.
- `SQLALCHEMY_DATABASE_URL` dạng `sqlite:///./app.db` nghĩa là file `app.db` nằm tại thư mục hiện tại khi chạy server.

---

### 4.2 Database Base — `app/db/base.py`

```python
from sqlalchemy.orm import declarative_base

Base = declarative_base()
```

- `Base` là class cha mà tất cả models kế thừa.
- SQLAlchemy dùng `Base.metadata` để biết cần tạo bảng nào khi chạy migration.
- File này **không import models** để tránh circular import.

---

### 4.3 Database Session — `app/db/session.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # bắt buộc với SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

| | Vai trò |
|---|---|
| `engine` | Kết nối vật lý tới file database |
| `SessionLocal` | Factory — mỗi lần gọi tạo ra 1 session mới |
| `check_same_thread: False` | SQLite mặc định không cho phép dùng từ nhiều thread — cần tắt để FastAPI hoạt động |

---

### 4.4 Models — `app/models/`

Models là ánh xạ giữa Python class và bảng trong database.

**`author.py`**
```python
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from app.db.base import Base

class Author(Base):
    __tablename__ = "authors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    biography = Column(Text, nullable=True)

    books = relationship("Book", back_populates="author")
```

**`category.py`**
```python
class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)

    books = relationship("Book", back_populates="category")
```

**`book.py`**
```python
class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    published_year = Column(Integer, nullable=True)
    author_id = Column(Integer, ForeignKey("authors.id", ondelete="RESTRICT"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False)

    author = relationship("Author", back_populates="books")
    category = relationship("Category", back_populates="books")
```

- `ForeignKey` tạo ràng buộc khóa ngoại trong database.
- `ondelete="RESTRICT"` ngăn xóa Author/Category khi còn Book liên kết.
- `relationship()` là Python object — không tạo cột trong DB, chỉ giúp truy cập `book.author` tiện lợi.

---

### 4.5 Schemas — `app/schemas/`

Schemas dùng Pydantic để validate input/output. Mỗi entity có 4 class theo pattern:

```
Base       → các field dùng chung
 ├── Create  → dùng khi POST (tạo mới)
 ├── Update  → dùng khi PUT (cập nhật, tất cả optional)
 └── Response (tên entity) → dùng khi trả về cho client, có id và nested objects
```

**`author.py`**
```python
from pydantic import BaseModel, ConfigDict

class AuthorBase(BaseModel):
    name: str
    biography: str | None = None

class AuthorCreate(AuthorBase):    # POST — name bắt buộc
    pass

class AuthorUpdate(BaseModel):     # PUT — tất cả optional
    name: str | None = None
    biography: str | None = None

class AuthorInDBBase(AuthorBase):
    id: int
    model_config = ConfigDict(from_attributes=True)  # cho phép đọc từ ORM object

class Author(AuthorInDBBase):      # Response schema
    pass
```

**`book.py`** — Response trả về object Author và Category lồng vào, không chỉ id:
```python
class Book(BookBase):
    id: int
    author: Author       # object đầy đủ, không chỉ author_id
    category: Category
    model_config = ConfigDict(from_attributes=True)
```

> `from_attributes=True` (Pydantic v2) tương đương `orm_mode=True` (Pydantic v1) — cho phép Pydantic đọc dữ liệu từ SQLAlchemy object thay vì chỉ từ dict.

---

### 4.6 Dependencies — `app/api/deps.py`

```python
from collections.abc import Generator
from sqlalchemy.orm import Session
from app.db.session import SessionLocal

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db      # trả session cho endpoint dùng, dừng tại đây
    finally:
        db.close()    # chạy sau khi endpoint xử lý xong, dù lỗi hay không
```

- `yield` biến hàm thành generator — FastAPI dùng pattern này để đảm bảo `db.close()` **luôn được gọi** dù endpoint có lỗi.
- Khai báo `Depends(get_db)` trong endpoint sẽ tự động inject session mới cho mỗi request.

---

### 4.7 Endpoints — `app/api/endpoints/`

Pattern CRUD chuẩn cho mỗi entity. Ví dụ `categories.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.models import Category
from app.schemas.category import CategoryCreate, CategoryUpdate, Category as CategorySchema

router = APIRouter()

# GET /categories — lấy danh sách
@router.get("/", response_model=List[CategorySchema])
def list_categories(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Category).offset(skip).limit(limit).all()

# GET /categories/{id} — lấy 1 record
@router.get("/{category_id}", response_model=CategorySchema)
def get_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category

# POST /categories — tạo mới
@router.post("/", response_model=CategorySchema, status_code=status.HTTP_201_CREATED)
def create_category(category_in: CategoryCreate, db: Session = Depends(get_db)):
    if db.query(Category).filter(Category.name == category_in.name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category with this name already exists")
    category = Category(name=category_in.name, description=category_in.description)
    db.add(category)
    db.commit()
    db.refresh(category)  # lấy lại data từ DB (bao gồm id vừa được gán)
    return category

# PUT /categories/{id} — cập nhật
@router.put("/{category_id}", response_model=CategorySchema)
def update_category(category_id: int, category_in: CategoryUpdate, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    if category_in.name is not None:
        category.name = category_in.name
    if category_in.description is not None:
        category.description = category_in.description
    db.commit()
    db.refresh(category)
    return category

# DELETE /categories/{id} — xóa
@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    db.delete(category)
    db.commit()
    return None
```

**Luồng xử lý mỗi request:**
```
Client gửi request
  → FastAPI validate input theo schema (CategoryCreate)
  → Depends(get_db) tạo session mới
  → Endpoint xử lý logic, truy vấn DB
  → FastAPI serialize output theo response_model
  → get_db finally: db.close()
  → Trả response về client
```

---

### 4.8 Main App — `app/main.py`

```python
from fastapi import FastAPI

app = FastAPI(
    title="Book management API",
    description="A simple API for managing books",
    version="1.0.0",
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Book management API"}

from app.api.endpoints import books, authors, categories

app.include_router(books.router, prefix="/books", tags=["Books"])
app.include_router(authors.router, prefix="/authors", tags=["Authors"])
app.include_router(categories.router, prefix="/categories", tags=["Categories"])
```

- `prefix="/books"` gắn tiền tố URL — endpoint `@router.get("/")` sẽ thành `GET /books/`.
- `tags=["Books"]` nhóm các endpoint trên Swagger UI.

---

## 5. Database Migration với Alembic

Alembic quản lý thay đổi schema database theo thời gian (giống `php artisan migrate` trong Laravel).

```bash
# Tạo migration tự động từ models (lần đầu)
alembic revision --autogenerate -m "Init tables"
# → Tạo file migrations/versions/xxxx_init_tables.py

# Áp dụng migration vào database
alembic upgrade head

# Xem lịch sử migration
alembic history

# Rollback 1 bước
alembic downgrade -1

# Rollback về đầu
alembic downgrade base
```

**Quy trình khi thêm cột mới:**
```bash
# 1. Thêm cột vào model Python
# 2. Tạo migration
alembic revision --autogenerate -m "Add cover_image to books"
# 3. Kiểm tra file migration vừa tạo
# 4. Áp dụng
alembic upgrade head
```

---

## 6. Chạy server

```bash
# Development (có hot-reload)
fastapi dev app/main.py

# Production
fastapi run app/main.py
```

Sau khi chạy:
- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 7. API Reference

### Categories

| Method | URL | Mô tả |
|---|---|---|
| GET | `/categories` | Lấy danh sách categories |
| GET | `/categories/{id}` | Lấy 1 category |
| POST | `/categories` | Tạo mới category |
| PUT | `/categories/{id}` | Cập nhật category |
| DELETE | `/categories/{id}` | Xóa category |

### Authors

| Method | URL | Mô tả |
|---|---|---|
| GET | `/authors` | Lấy danh sách authors |
| GET | `/authors/{id}` | Lấy 1 author |
| POST | `/authors` | Tạo mới author |
| PUT | `/authors/{id}` | Cập nhật author |
| DELETE | `/authors/{id}` | Xóa author |

### Books

| Method | URL | Mô tả |
|---|---|---|
| GET | `/books` | Lấy danh sách books (kèm author và category) |
| GET | `/books/{id}` | Lấy 1 book |
| POST | `/books` | Tạo mới book |
| PUT | `/books/{id}` | Cập nhật book |
| DELETE | `/books/{id}` | Xóa book |

**Ví dụ tạo book:**
```bash
curl -X POST http://localhost:8000/books \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Chí Phèo",
    "description": "Truyện ngắn của Nam Cao",
    "published_year": 1941,
    "author_id": 1,
    "category_id": 1
  }'
```

**Response:**
```json
{
  "id": 1,
  "title": "Chí Phèo",
  "description": "Truyện ngắn của Nam Cao",
  "published_year": 1941,
  "author_id": 1,
  "category_id": 1,
  "author": {
    "id": 1,
    "name": "Nam Cao",
    "biography": null
  },
  "category": {
    "id": 1,
    "name": "Văn học",
    "description": null
  }
}
```

---

## Query Parameters

Tất cả endpoint GET danh sách đều hỗ trợ phân trang:

| Param | Mặc định | Mô tả |
|---|---|---|
| `skip` | 0 | Bỏ qua N record đầu |
| `limit` | 100 | Tối đa N record trả về |

```bash
# Lấy trang 2, mỗi trang 10 records
GET /books?skip=10&limit=10
```
