"""Business logic cho AI module — orchestrate giữa router và tasks.

  router.py  →  service.py  →  tasks.py  →  OpenAI API
  (HTTP)        (logic)        (API call)

Không gọi HTTP trực tiếp — delegate xuống tasks.py.
Không hardcode giá trị — lấy từ settings.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.ai import tasks
from app.common.redis import cache_delete, cache_get, cache_key, cache_set
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
from app.core.config import settings
from app.repositories import BookRepository
from app.schemas.book import Book as BookSchema

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _handle_ai_error(e: Exception) -> None:
    """Convert AI errors → HTTP errors có message rõ ràng."""
    if isinstance(e, AINotConfiguredError):
        raise HTTPException(status_code=503, detail=str(e))
    logger.error("ai.service.error", extra={"error": str(e), "type": type(e).__name__})
    raise HTTPException(status_code=502, detail=f"OpenAI API lỗi: {str(e)}")


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── LLM services ───────────────────────────────────────────────────────────────

async def summarize(book_id: int, db: Session) -> SummarizeResponse:
    # Pattern 1: AI Result Cache — học từ vuonglearning ai-service/cache.py
    # vuonglearning: cache web search results, image summaries để tránh gọi lại OpenAI
    # book-management: cache summary 1h — cùng book, cùng nội dung → không cần gọi lại
    key = cache_key("ai", "summary", book_id)
    cached = await cache_get(key)
    if cached:
        logger.info("ai.service.summarize.cache_hit", extra={"book_id": book_id})
        return SummarizeResponse(**cached)

    repo = BookRepository(db)
    book = repo.get_by_id(book_id)
    prompt = build_summarize_prompt(title=book.title, author=book.author.name, description=book.description)

    try:
        summary = await tasks._call_chat(prompt, max_tokens=settings.openai_max_tokens_summarize)
    except Exception as e:
        _handle_ai_error(e)

    result = SummarizeResponse(book_id=book.id, title=book.title, summary=summary)
    await cache_set(key, result.model_dump(), ttl=settings.cache_ai_result_ttl)
    logger.info("ai.service.summarize.done", extra={"book_id": book_id})
    return result


async def generate_description(book_id: int, save: bool, db: Session) -> GenerateDescriptionResponse:
    # Cache chỉ khi không save — nếu save=True thì generate mới để user nhận kết quả mới nhất
    key = cache_key("ai", "description", book_id)
    if not save:
        cached = await cache_get(key)
        if cached:
            logger.info("ai.service.description.cache_hit", extra={"book_id": book_id})
            return GenerateDescriptionResponse(**cached)

    repo = BookRepository(db)
    book = repo.get_by_id(book_id)
    prompt = build_generate_description_prompt(title=book.title, author=book.author.name, category=book.category.name)

    try:
        description = await tasks._call_chat(
            prompt,
            max_tokens=settings.openai_max_tokens_describe,
            temperature=settings.openai_temperature_creative,
        )
    except Exception as e:
        _handle_ai_error(e)

    if save:
        repo.update_description(book_id, description)
        await cache_delete(key)   # invalidate — description đã thay đổi trong DB
        logger.info("ai.service.description.saved", extra={"book_id": book_id})

    result = GenerateDescriptionResponse(
        book_id=book.id, title=book.title, generated_description=description, saved=save
    )
    if not save:
        await cache_set(key, result.model_dump(), ttl=settings.cache_ai_result_ttl)
    return result


# ── Embedding services ─────────────────────────────────────────────────────────

async def embed_book(book_id: int, db: Session) -> EmbedBookResponse:
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
    """Batch embed — sleep giữa các calls theo settings.ai_embed_rate_limit_sleep."""
    repo = BookRepository(db)
    pending = [b for b in repo.list(skip=0, limit=10000) if not b.embedding]

    if not pending:
        return EmbedAllResponse(total=0, success=0, failed=0, message="Tất cả books đã có embedding")

    success, failed = 0, 0
    for book in pending:
        try:
            text = build_embedding_text(book.title, book.description)
            embedding = await tasks._call_embedding(text)
            repo.save_embedding(book.id, json.dumps(embedding))
            success += 1
            await asyncio.sleep(settings.ai_embed_rate_limit_sleep)  # từ config, không hardcode
        except Exception as e:
            logger.warning("ai.service.embed_all.failed", extra={"book_id": book.id, "error": str(e)})
            failed += 1

    logger.info("ai.service.embed_all.done", extra={"success": success, "failed": failed})
    return EmbedAllResponse(
        total=len(pending), success=success, failed=failed,
        message=f"Embed xong {success}/{len(pending)} books",
    )


async def semantic_search(query: str, top_k: int, db: Session) -> SemanticSearchResponse:
    """Tìm kiếm theo nghĩa — threshold lấy từ settings.ai_semantic_search_threshold."""
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

    scored = sorted(
        [(_cosine_similarity(query_embedding, json.loads(b.embedding)), b) for b in books_with_embedding],
        key=lambda x: x[0],
        reverse=True,
    )

    results = [
        SearchResult(book=BookSchema.model_validate(book), similarity_score=round(score, 4))
        for score, book in scored[:top_k]
        if score > settings.ai_semantic_search_threshold  # từ config
    ]

    logger.info("ai.service.semantic_search.done", extra={"query": query, "results": len(results)})
    return SemanticSearchResponse(query=query, results=results, total=len(results))


async def similar_books(book_id: int, top_k: int, db: Session) -> SimilarBooksResponse:
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
