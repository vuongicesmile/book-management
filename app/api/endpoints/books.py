import asyncio
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse
from typing import List

from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.decorators import log_duration, validate_pagination
from app.core.notifications import notify_book_created, notify_book_deleted, notify_books_imported
from app.repositories import AuthorRepository, BookRepository, CategoryRepository
from app.schemas.book import BookCreate, BookUpdate, Book as BookSchema

router = APIRouter()


# ── async def + asyncio.create_task ───────────────────────────────────────────
#
# Trước (sync):
#   def create_book(...):
#       background_tasks.add_task(notify_book_created, ...)
#
# Sau (async):
#   async def create_book(...):
#       asyncio.create_task(notify_book_created(...))
#
# Tại sao async def tốt hơn?
#   - Không block event loop khi chờ I/O (DB, HTTP, file)
#   - asyncio.create_task() = coroutine chạy song song, không cần chờ
#   - Giống hệt pattern vuonglearning dùng trong ai_proxy/service.py
#
# Lưu ý: DB vẫn là sync SQLAlchemy (SQLite, learning project).
# Production với PostgreSQL → dùng AsyncSession + await db.execute(...)


@router.get("/", response_model=List[BookSchema])
@log_duration
@validate_pagination()
async def list_books(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Lấy danh sách tất cả books, hỗ trợ phân trang."""
    return BookRepository(db).list(skip, limit)


@router.get("/search", response_model=List[BookSchema])
@log_duration
async def search_books(q: str, db: Session = Depends(get_db)):
    """Tìm kiếm books theo title hoặc description."""
    return BookRepository(db).search(q)


@router.get("/stats")
@log_duration
async def book_stats(db: Session = Depends(get_db)):
    """Thống kê tổng quan books."""
    return BookRepository(db).stats()


@router.get("/export/titles")
@log_duration
async def export_titles(db: Session = Depends(get_db)):
    """Export danh sách titles."""
    repo = BookRepository(db)
    titles = [title for title in repo.iter_as_csv() if not title.startswith("id,")]
    return {"total": len(titles), "titles": [t.split(",")[1] for t in titles]}


@router.get("/export/csv")
async def export_csv(db: Session = Depends(get_db)):
    """Stream CSV response dùng generator."""
    return StreamingResponse(
        BookRepository(db).iter_as_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=books.csv"},
    )


@router.post("/import/csv", status_code=status.HTTP_201_CREATED)
async def import_books_from_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import nhiều books từ file CSV upload.

    Sau khi import xong → asyncio.create_task() gửi notification (fire-and-forget).

    Format CSV:
        title,description,year,author_id,category_id
        Clean Code,,2008,1,1
        The Pragmatic Programmer,A must read,1999,2,1
    """
    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))

    repo = BookRepository(db)
    created, skipped = [], []

    for row in reader:
        book_in = BookCreate.from_csv_row(row)
        if repo.exists_by_title(book_in.title):
            skipped.append(book_in.title)
            continue
        repo.create(**book_in.model_dump())
        created.append(book_in.title)

    # asyncio.create_task() — fire-and-forget, response trả về ngay
    # notify_books_imported() là async def → phải gọi như coroutine: func(args)
    asyncio.create_task(notify_books_imported(len(created), len(skipped), created))

    return {
        "created": len(created),
        "skipped": len(skipped),
        "created_titles": created,
        "skipped_titles": skipped,
    }


@router.get("/{book_id}", response_model=BookSchema)
async def get_book(book_id: int, db: Session = Depends(get_db)):
    return BookRepository(db).get_by_id(book_id)


@router.post("/", response_model=BookSchema, status_code=status.HTTP_201_CREATED)
async def create_book(book_in: BookCreate, db: Session = Depends(get_db)):
    repo = BookRepository(db)
    if repo.exists_by_title(book_in.title):
        raise HTTPException(status_code=400, detail="Book with this title already exists")
    AuthorRepository(db).get_by_id(book_in.author_id)
    CategoryRepository(db).get_by_id(book_in.category_id)
    book = repo.create(**book_in.model_dump())

    # asyncio.create_task() — chạy notify_book_created song song, không chờ
    # So sánh vuonglearning:
    #   asyncio.create_task(_post_stream_process(chat_id=..., user_id=..., ...))
    asyncio.create_task(notify_book_created(book.id, book.title, book.author_id))

    return book


@router.put("/{book_id}", response_model=BookSchema)
async def update_book(book_id: int, book_in: BookUpdate, db: Session = Depends(get_db)):
    return BookRepository(db).update(book_id, **book_in.model_dump(exclude_unset=True))


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(book_id: int, db: Session = Depends(get_db)):
    BookRepository(db).delete(book_id)

    # Fire-and-forget notify sau khi xóa
    asyncio.create_task(notify_book_deleted(book_id))
