"""Business logic cho AI module — tầng giữa giữa router và tasks.

Pattern từ ilmuchat: ai_proxy/service.py orchestrate toàn bộ flow.
  router.py  →  service.py  →  tasks.py  →  OpenAI API
  (HTTP)        (logic)         (API call)

Nguyên tắc:
  - Không gọi HTTP trực tiếp — delegate xuống tasks.py
  - Xử lý error, logging, DB operations ở đây
  - Router chỉ gọi 1 function từ service, không làm gì thêm
"""
from __future__ import annotations

import asyncio
import json
import logging
import math

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.ai import tasks
from app.ai.prompts import (
    build_embedding_text,
    build_generate_description_prompt,
    build_summarize_prompt,
)
from app.ai.schemas import (
    EmbedAllResponse,
    EmbedBookResponse,
    GenerateDescriptionResponse,
    SearchResult,
    SemanticSearchResponse,
    SimilarBooksResponse,
    SummarizeResponse,
)
from app.ai.tasks import AINotConfiguredError
from app.repositories import BookRepository
from app.schemas.book import Book as BookSchema

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _handle_ai_error(e: Exception) -> None:
    """Convert AI errors → HTTP errors có message rõ ràng.

    Pattern từ ilmuchat: error handler tập trung, không scatter qua endpoints.
    """
    if isinstance(e, AINotConfiguredError):
        raise HTTPException(status_code=503, detail=str(e))
    logger.error("ai.service.error", extra={"error": str(e), "type": type(e).__name__})
    raise HTTPException(status_code=502, detail=f"OpenAI API lỗi: {str(e)}")


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity — đo độ tương đồng giữa 2 vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── LLM services ──────────────────────────────────────────────────────────────

async def summarize(book_id: int, db: Session) -> SummarizeResponse:
    """Tóm tắt sách dùng LLM."""
    repo = BookRepository(db)
    book = repo.get_by_id(book_id)

    prompt = build_summarize_prompt(
        title=book.title,
        author=book.author.name,
        description=book.description,
    )

    try:
        summary = await tasks._call_chat(prompt, max_tokens=200)
    except Exception as e:
        _handle_ai_error(e)

    logger.info("ai.service.summarize.done", extra={"book_id": book_id, "title": book.title})

    return SummarizeResponse(book_id=book.id, title=book.title, summary=summary)


async def generate_description(book_id: int, save: bool, db: Session) -> GenerateDescriptionResponse:
    """Viết description cho sách dùng LLM. save=True → lưu vào DB."""
    repo = BookRepository(db)
    book = repo.get_by_id(book_id)

    prompt = build_generate_description_prompt(
        title=book.title,
        author=book.author.name,
        category=book.category.name,
    )

    try:
        description = await tasks._call_chat(prompt, max_tokens=250, temperature=0.8)
    except Exception as e:
        _handle_ai_error(e)

    if save:
        repo.update_description(book_id, description)
        logger.info("ai.service.description.saved", extra={"book_id": book_id})

    return GenerateDescriptionResponse(
        book_id=book.id,
        title=book.title,
        generated_description=description,
        saved=save,
    )


# ── Embedding services ────────────────────────────────────────────────────────

async def embed_book(book_id: int, db: Session) -> EmbedBookResponse:
    """Tạo và lưu embedding cho 1 book."""
    repo = BookRepository(db)
    book = repo.get_by_id(book_id)

    text = build_embedding_text(book.title, book.description)

    try:
        embedding = await tasks._call_embedding(text)
    except Exception as e:
        _handle_ai_error(e)

    repo.save_embedding(book_id, json.dumps(embedding))

    return EmbedBookResponse(
        book_id=book.id,
        title=book.title,
        embedding_dimensions=len(embedding),
        message=f"Đã lưu embedding {len(embedding)} chiều",
    )


async def embed_all_books(db: Session) -> EmbedAllResponse:
    """Batch embed tất cả books chưa có embedding.

    Pattern từ ilmuchat: background tasks với asyncio.create_task.
    Dùng asyncio.sleep(0.1) giữa các calls để tránh rate limit.
    """
    repo = BookRepository(db)
    all_books = repo.list(skip=0, limit=10000)
    pending = [b for b in all_books if not b.embedding]

    if not pending:
        return EmbedAllResponse(total=0, success=0, failed=0, message="Tất cả books đã có embedding")

    success, failed = 0, 0
    for book in pending:
        try:
            text = build_embedding_text(book.title, book.description)
            embedding = await tasks._call_embedding(text)
            repo.save_embedding(book.id, json.dumps(embedding))
            success += 1
            await asyncio.sleep(0.1)  # tránh OpenAI rate limit
        except Exception as e:
            logger.warning("ai.service.embed_all.failed", extra={"book_id": book.id, "error": str(e)})
            failed += 1

    logger.info("ai.service.embed_all.done", extra={"success": success, "failed": failed})

    return EmbedAllResponse(
        total=len(pending),
        success=success,
        failed=failed,
        message=f"Embed xong {success}/{len(pending)} books",
    )


async def semantic_search(query: str, top_k: int, db: Session) -> SemanticSearchResponse:
    """Tìm kiếm theo nghĩa dùng cosine similarity."""
    try:
        query_embedding = await tasks._call_embedding(query)
    except Exception as e:
        _handle_ai_error(e)

    repo = BookRepository(db)
    books_with_embedding = repo.get_books_with_embedding()

    if not books_with_embedding:
        raise HTTPException(
            status_code=404,
            detail="Chưa có book nào được embed. Chạy POST /ai/books/embed-all trước.",
        )

    # Tính similarity và sort
    scored = sorted(
        [
            (_cosine_similarity(query_embedding, json.loads(b.embedding)), b)
            for b in books_with_embedding
        ],
        key=lambda x: x[0],
        reverse=True,
    )

    results = [
        SearchResult(book=BookSchema.model_validate(book), similarity_score=round(score, 4))
        for score, book in scored[:top_k]
        if score > 0.3
    ]

    logger.info("ai.service.semantic_search.done", extra={"query": query, "results": len(results)})

    return SemanticSearchResponse(query=query, results=results, total=len(results))


async def similar_books(book_id: int, top_k: int, db: Session) -> SimilarBooksResponse:
    """Gợi ý sách tương tự dựa trên embedding similarity."""
    repo = BookRepository(db)
    book = repo.get_by_id(book_id)

    if not book.embedding:
        raise HTTPException(
            status_code=422,
            detail=f"Book '{book.title}' chưa được embed. Chạy POST /ai/books/{book_id}/embed trước.",
        )

    book_embedding = json.loads(book.embedding)
    others = [b for b in repo.get_books_with_embedding() if b.id != book_id]

    scored = sorted(
        [(_cosine_similarity(book_embedding, json.loads(b.embedding)), b) for b in others],
        key=lambda x: x[0],
        reverse=True,
    )

    similar = [
        SearchResult(book=BookSchema.model_validate(b), similarity_score=round(score, 4))
        for score, b in scored[:top_k]
    ]

    return SimilarBooksResponse(book_id=book.id, title=book.title, similar_books=similar)
