"""AI endpoints — Bài 102-110 áp dụng thực tế.

5 endpoints:
  POST /ai/books/{id}/summarize           → Bài 102-104: LLM tóm tắt sách
  POST /ai/books/{id}/generate-description → Bài 102-104: LLM viết description
  POST /ai/books/{id}/embed               → Bài 108: Tạo và lưu embedding
  GET  /ai/books/search/semantic          → Bài 108: Tìm kiếm theo nghĩa
  GET  /ai/books/{id}/similar             → Bài 108: Gợi ý sách tương tự
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.ai import (
    AINotConfiguredError,
    cosine_similarity,
    embedding_to_json,
    generate_description,
    get_embedding,
    json_to_embedding,
    summarize_book,
)
from app.repositories import BookRepository
from app.schemas.ai import (
    EmbedBookResponse,
    GenerateDescriptionResponse,
    SemanticSearchResponse,
    SemanticSearchResult,
    SimilarBooksResponse,
    SummarizeResponse,
)
from app.schemas.book import Book as BookSchema

router = APIRouter()


def _handle_ai_error(e: Exception) -> None:
    """Convert AI errors thành HTTP errors rõ ràng."""
    if isinstance(e, AINotConfiguredError):
        raise HTTPException(status_code=503, detail=str(e))
    raise HTTPException(status_code=502, detail=f"OpenAI API lỗi: {str(e)}")


# ── Bài 102-104: LLM endpoints ────────────────────────────────────────────────


@router.post("/books/{book_id}/summarize", response_model=SummarizeResponse)
async def summarize(book_id: int, db: Session = Depends(get_db)):
    """Dùng LLM tóm tắt sách thành 2-3 câu.

    Bài 102-104: Gọi OpenAI chat/completions API.
    Sách phải tồn tại — 404 nếu không tìm thấy.
    503 nếu OPENAI_API_KEY chưa cấu hình.
    """
    repo = BookRepository(db)
    book = repo.get_by_id(book_id)

    try:
        summary = await summarize_book(
            title=book.title,
            description=book.description,
            author=book.author.name,
        )
    except Exception as e:
        _handle_ai_error(e)

    return SummarizeResponse(
        book_id=book.id,
        title=book.title,
        summary=summary,
    )


@router.post("/books/{book_id}/generate-description", response_model=GenerateDescriptionResponse)
async def gen_description(
    book_id: int,
    save: bool = Query(default=False, description="True → lưu description vào DB"),
    db: Session = Depends(get_db),
):
    """Dùng LLM viết description cho sách.

    Bài 102-104: LLM generate content dựa trên title + author + category.
    Query param `save=true` → tự động lưu vào DB luôn.
    """
    repo = BookRepository(db)
    book = repo.get_by_id(book_id)

    try:
        description = await generate_description(
            title=book.title,
            author=book.author.name,
            category=book.category.name,
        )
    except Exception as e:
        _handle_ai_error(e)

    if save:
        repo.update_description(book_id, description)

    return GenerateDescriptionResponse(
        book_id=book.id,
        title=book.title,
        generated_description=description,
    )


# ── Bài 108: Embedding endpoints ──────────────────────────────────────────────


@router.post("/books/{book_id}/embed", response_model=EmbedBookResponse)
async def embed_book(book_id: int, db: Session = Depends(get_db)):
    """Tạo và lưu vector embedding cho sách.

    Bài 108: Text → vector 1536 chiều.
    Text input = title + description (càng nhiều context càng tốt).
    Embedding được lưu vào DB để dùng cho search và similar.
    """
    repo = BookRepository(db)
    book = repo.get_by_id(book_id)

    # Tạo text input từ title + description
    text = book.title
    if book.description:
        text += f". {book.description}"

    try:
        embedding = await get_embedding(text)
    except Exception as e:
        _handle_ai_error(e)

    # Lưu embedding vào DB dưới dạng JSON string
    repo.save_embedding(book_id, embedding_to_json(embedding))

    return EmbedBookResponse(
        book_id=book.id,
        title=book.title,
        embedding_dimensions=len(embedding),
        message=f"Đã lưu embedding {len(embedding)} chiều",
    )


@router.post("/books/embed-all", response_model=dict)
async def embed_all_books(db: Session = Depends(get_db)):
    """Tạo embedding cho tất cả books chưa có embedding.

    Bài 108: Batch embedding — cần chạy 1 lần để setup semantic search.
    Dùng asyncio.create_task (Bài 104) để tránh block quá lâu.
    """
    repo = BookRepository(db)
    all_books = repo.list(skip=0, limit=10000)
    books_without_embedding = [b for b in all_books if not b.embedding]

    if not books_without_embedding:
        return {"message": "Tất cả books đã có embedding", "count": 0}

    success, failed = 0, 0
    for book in books_without_embedding:
        try:
            text = book.title
            if book.description:
                text += f". {book.description}"
            embedding = await get_embedding(text)
            repo.save_embedding(book.id, embedding_to_json(embedding))
            success += 1
            await asyncio.sleep(0.1)  # tránh rate limit OpenAI
        except Exception:
            failed += 1

    return {
        "total": len(books_without_embedding),
        "success": success,
        "failed": failed,
    }


@router.get("/books/search/semantic", response_model=SemanticSearchResponse)
async def semantic_search(
    q: str = Query(min_length=1, description="Từ khóa tìm kiếm theo nghĩa"),
    top_k: int = Query(default=5, ge=1, le=20, description="Số kết quả trả về"),
    db: Session = Depends(get_db),
):
    """Tìm kiếm sách theo nghĩa, không phải từ khoá chính xác.

    Bài 108: Semantic Search với Vector Embeddings.

    Khác biệt với keyword search:
      keyword: "python web" → chỉ tìm sách có đúng chữ "python web"
      semantic: "python web" → tìm "FastAPI development", "Django guide"
                               vì các câu này có vector gần nhau

    Yêu cầu: books phải đã được embed trước (POST /ai/books/{id}/embed).
    """
    # Tạo embedding cho query
    try:
        query_embedding = await get_embedding(q)
    except Exception as e:
        _handle_ai_error(e)

    # Lấy tất cả books có embedding từ DB
    repo = BookRepository(db)
    books_with_embedding = repo.get_books_with_embedding()

    if not books_with_embedding:
        raise HTTPException(
            status_code=404,
            detail="Chưa có book nào được embed. Chạy POST /ai/books/{id}/embed trước.",
        )

    # Tính cosine similarity giữa query và từng book
    scored: list[tuple[float, object]] = []
    for book in books_with_embedding:
        book_embedding = json_to_embedding(book.embedding)
        score = cosine_similarity(query_embedding, book_embedding)
        scored.append((score, book))

    # Sắp xếp theo score giảm dần, lấy top_k
    scored.sort(key=lambda x: x[0], reverse=True)
    top_results = scored[:top_k]

    results = [
        SemanticSearchResult(
            book=BookSchema.model_validate(book),
            similarity_score=round(score, 4),
        )
        for score, book in top_results
        if score > 0.3  # filter bỏ kết quả quá không liên quan
    ]

    return SemanticSearchResponse(
        query=q,
        results=results,
        total=len(results),
    )


@router.get("/books/{book_id}/similar", response_model=SimilarBooksResponse)
async def similar_books(
    book_id: int,
    top_k: int = Query(default=5, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """Gợi ý sách tương tự dựa trên embedding similarity.

    Bài 108: So sánh embedding của book này với tất cả books còn lại.
    Books phải đã được embed trước.
    """
    repo = BookRepository(db)
    book = repo.get_by_id(book_id)

    if not book.embedding:
        raise HTTPException(
            status_code=422,
            detail=f"Book '{book.title}' chưa được embed. Chạy POST /ai/books/{book_id}/embed trước.",
        )

    book_embedding = json_to_embedding(book.embedding)
    books_with_embedding = repo.get_books_with_embedding()

    # Tính similarity với tất cả books khác (bỏ qua chính nó)
    scored = []
    for other in books_with_embedding:
        if other.id == book_id:
            continue
        other_embedding = json_to_embedding(other.embedding)
        score = cosine_similarity(book_embedding, other_embedding)
        scored.append((score, other))

    scored.sort(key=lambda x: x[0], reverse=True)

    similar = [
        SemanticSearchResult(
            book=BookSchema.model_validate(b),
            similarity_score=round(score, 4),
        )
        for score, b in scored[:top_k]
    ]

    return SimilarBooksResponse(
        book_id=book.id,
        title=book.title,
        similar_books=similar,
    )
