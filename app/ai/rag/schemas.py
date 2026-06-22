"""Pydantic schemas cho RAG module."""
from __future__ import annotations

from app.schemas.base import AppModel


class IndexResponse(AppModel):
    book_id: int
    title: str
    total_pages: int
    total_chunks: int
    message: str


class RagSummarizeResponse(AppModel):
    book_id: int
    title: str
    summary: str
    chunks_used: int
    source_pages: list[int]


class AskRequest(AppModel):
    question: str


class AskResponse(AppModel):
    book_id: int
    title: str
    question: str
    answer: str
    chunks_used: int
    source_pages: list[int]


class IndexStatusResponse(AppModel):
    book_id: int
    title: str
    is_indexed: bool
    message: str
