"""RAG router — thin HTTP layer.

Endpoints:
  POST /ai/rag/books/{id}/index        — upload PDF + index vào ChromaDB
  GET  /ai/rag/books/{id}/index/status — kiểm tra đã index chưa
  POST /ai/rag/books/{id}/summarize    — RAG-based tóm tắt từ nội dung thật
  POST /ai/rag/books/{id}/ask          — hỏi bất kỳ câu hỏi về sách
  DELETE /ai/rag/books/{id}/index      — xóa index
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.ai.rag import service, vectorstore
from app.ai.rag.schemas import (
    AskRequest,
    AskResponse,
    IndexResponse,
    IndexStatusResponse,
    RagSummarizeResponse,
)
from app.api.deps import get_db
from app.repositories import BookRepository

router = APIRouter()


@router.post("/books/{book_id}/index", response_model=IndexResponse)
async def index_book(
    book_id: int,
    file: UploadFile = File(..., description="File PDF của sách"),
    db: Session = Depends(get_db),
):
    """Upload PDF và index vào ChromaDB.

    Bài 150: Document Loader (PyPDFLoader)
    Bài 151: Chunking (RecursiveCharacterTextSplitter)
    Bài 148+152: ChromaDB Vector Store
    """
    file_bytes = await file.read()
    return await service.index_book_pdf(book_id, file_bytes, file.filename, db)


@router.get("/books/{book_id}/index/status", response_model=IndexStatusResponse)
def index_status(book_id: int, db: Session = Depends(get_db)):
    """Kiểm tra book đã được index chưa."""
    repo = BookRepository(db)
    book = repo.get_by_id(book_id)
    is_indexed = vectorstore.collection_exists(book_id)
    return IndexStatusResponse(
        book_id=book_id,
        title=book.title,
        is_indexed=is_indexed,
        message="Đã index" if is_indexed else "Chưa index — upload PDF trước",
    )


@router.post("/books/{book_id}/summarize", response_model=RagSummarizeResponse)
async def rag_summarize(book_id: int, db: Session = Depends(get_db)):
    """Tóm tắt dựa trên nội dung thật của PDF.

    Bài 153: RAG Retrieval Execution
    Khác summarize thường: dùng chunks từ PDF, không chỉ title/description.
    """
    return await service.rag_summarize(book_id, db)


@router.post("/books/{book_id}/ask", response_model=AskResponse)
async def ask_book(book_id: int, body: AskRequest, db: Session = Depends(get_db)):
    """Hỏi bất kỳ câu hỏi về nội dung sách.

    Bài 145+147: Naive vs RAG Retrieval
    RAG chỉ lấy chunks liên quan — không nhét cả sách vào prompt.
    """
    return await service.ask_book(book_id, body.question, db)


@router.delete("/books/{book_id}/index", status_code=204)
def delete_index(book_id: int):
    """Xóa ChromaDB index của 1 book (để re-index với PDF mới)."""
    vectorstore.delete_index(book_id)
