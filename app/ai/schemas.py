"""Pydantic schemas cho AI module.

Pattern từ vuonglearning: ai_proxy/schemas.py chứa tất cả schemas của module.
Không đặt ở app/schemas/ chung — schemas thuộc về module nào thì ở trong module đó.
"""
from __future__ import annotations

from app.schemas.base import AppModel
from app.schemas.book import Book as BookSchema


class SummarizeResponse(AppModel):
    book_id: int
    title: str
    summary: str


class GenerateDescriptionResponse(AppModel):
    book_id: int
    title: str
    generated_description: str
    saved: bool = False


class EmbedBookResponse(AppModel):
    book_id: int
    title: str
    embedding_dimensions: int
    message: str


class EmbedAllResponse(AppModel):
    total: int
    success: int
    failed: int
    message: str


class SearchResult(AppModel):
    """1 kết quả trong semantic search hoặc similar books."""
    book: BookSchema
    similarity_score: float


class SemanticSearchResponse(AppModel):
    query: str
    results: list[SearchResult]
    total: int


class SimilarBooksResponse(AppModel):
    book_id: int
    title: str
    similar_books: list[SearchResult]
