"""Schemas cho AI endpoints — Bài 90-101 Pydantic áp dụng vào AI responses."""
from __future__ import annotations

from app.schemas.base import AppModel
from app.schemas.book import Book as BookSchema


class SummarizeResponse(AppModel):
    """Response của POST /ai/books/{id}/summarize."""
    book_id: int
    title: str
    summary: str


class GenerateDescriptionResponse(AppModel):
    """Response của POST /ai/books/{id}/generate-description."""
    book_id: int
    title: str
    generated_description: str


class EmbedBookResponse(AppModel):
    """Response của POST /ai/books/{id}/embed."""
    book_id: int
    title: str
    embedding_dimensions: int
    message: str


class SemanticSearchResponse(AppModel):
    """Response của GET /ai/books/search/semantic."""
    query: str
    results: list[SemanticSearchResult]
    total: int


class SemanticSearchResult(AppModel):
    """1 kết quả trong semantic search."""
    book: BookSchema
    similarity_score: float   # 0.0 → 1.0, cao hơn = giống hơn


class SimilarBooksResponse(AppModel):
    """Response của GET /ai/books/{id}/similar."""
    book_id: int
    title: str
    similar_books: list[SemanticSearchResult]


# Fix forward reference — SemanticSearchResponse dùng SemanticSearchResult
SemanticSearchResponse.model_rebuild()
SimilarBooksResponse.model_rebuild()
