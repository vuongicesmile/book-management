"""AI router — thin HTTP layer, chỉ gọi service functions.

Pattern từ vuonglearning: ai_proxy/router.py imports từ schemas, service, tasks.
Router không chứa business logic — chỉ:
  1. Parse HTTP request
  2. Gọi service function
  3. Return response

So sánh với vuonglearning router.py:
  router.py → service.proxy_chat_completion(body, user, request)
  (thin)       (toàn bộ logic ở service)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.ai import schemas, service
from app.api.deps import get_db
from app.common.rate_limit import check_ai_rate_limit

router = APIRouter()


# ── LLM endpoints ─────────────────────────────────────────────────────────────
# Pattern 2: Rate Limiting — học từ vuonglearning rate_limit.py
# vuonglearning: per-IP limit cho /auth/signin, /auth/signup
# book-management: per-IP limit cho AI endpoints (bảo vệ OpenAI cost)

@router.post("/books/{book_id}/summarize", response_model=schemas.SummarizeResponse)
async def summarize(book_id: int, request: Request, db: Session = Depends(get_db)):
    """Dùng LLM tóm tắt sách. Rate limited: 20 req/60s per IP."""
    await check_ai_rate_limit(request)  # 429 nếu vượt limit
    return await service.summarize(book_id, db)


@router.post("/books/{book_id}/generate-description", response_model=schemas.GenerateDescriptionResponse)
async def gen_description(
    book_id: int,
    request: Request,
    save: bool = Query(default=False, description="True → lưu description vào DB"),
    db: Session = Depends(get_db),
):
    """Dùng LLM viết description cho sách. Rate limited."""
    await check_ai_rate_limit(request)
    return await service.generate_description(book_id, save, db)


# ── Embedding endpoints ────────────────────────────────────────────────────────

@router.post("/books/{book_id}/embed", response_model=schemas.EmbedBookResponse)
async def embed_book(book_id: int, request: Request, db: Session = Depends(get_db)):
    """Tạo và lưu vector embedding 1536 chiều cho sách. Rate limited."""
    await check_ai_rate_limit(request)
    return await service.embed_book(book_id, db)


@router.post("/books/embed-all", response_model=schemas.EmbedAllResponse)
async def embed_all(request: Request, db: Session = Depends(get_db)):
    """Batch embed tất cả books chưa có embedding. Rate limited."""
    await check_ai_rate_limit(request)
    return await service.embed_all_books(db)


@router.get("/books/search/semantic", response_model=schemas.SemanticSearchResponse)
async def semantic_search(
    q: str = Query(min_length=1, description="Từ khóa tìm kiếm theo nghĩa"),
    top_k: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Tìm kiếm sách theo nghĩa, không phải từ khoá chính xác."""
    return await service.semantic_search(q, top_k, db)


@router.get("/books/{book_id}/similar", response_model=schemas.SimilarBooksResponse)
async def similar_books(
    book_id: int,
    top_k: int = Query(default=5, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """Gợi ý sách tương tự dựa trên embedding similarity."""
    return await service.similar_books(book_id, top_k, db)
