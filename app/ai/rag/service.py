"""Bài 143-153: RAG Pipeline — orchestrate toàn bộ flow.

Indexing flow  (bài 146):  PDF → load → split → embed → ChromaDB
Retrieval flow (bài 147):  query → embed → similarity search → top-k chunks
Generation     (bài 153):  chunks + prompt → LLM → answer

Naive approach (bài 145): nhét toàn bộ sách vào prompt → vượt context window, tốn token.
RAG fix: chỉ lấy đúng N chunks liên quan nhất → context ngắn, chính xác hơn.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.ai.rag import loader, splitter, vectorstore
from app.ai.rag.schemas import (
    AskResponse,
    IndexResponse,
    RagSummarizeResponse,
)
from app.core.config import settings
from app.repositories import BookRepository

logger = logging.getLogger(__name__)


# ── Indexing ───────────────────────────────────────────────────────────────────

async def index_book_pdf(book_id: int, file_bytes: bytes, filename: str, db: Session) -> IndexResponse:
    """Bài 146 — Indexing Workflow.

    1. Lưu PDF lên disk
    2. Load PDF → Documents (LangChain PyPDFLoader)
    3. Split → chunks (RecursiveCharacterTextSplitter)
    4. Embed + store vào ChromaDB
    """
    repo = BookRepository(db)
    book = repo.get_by_id(book_id)

    # 1. Lưu file
    upload_dir = Path(settings.rag_upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = upload_dir / f"book_{book_id}.pdf"
    pdf_path.write_bytes(file_bytes)

    # 2. Load PDF → Documents
    try:
        docs = loader.load_pdf(pdf_path)
    except Exception as e:
        pdf_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Không đọc được PDF: {e}")

    # 3. Split → chunks
    chunks = splitter.split_documents(docs)

    # 4. Nếu đã index rồi → xóa index cũ trước
    if vectorstore.collection_exists(book_id):
        vectorstore.delete_index(book_id)

    # 5. Embed + store
    try:
        total_chunks = vectorstore.index_chunks(book_id, chunks)
    except Exception as e:
        logger.error("rag.index.failed", extra={"book_id": book_id, "error": str(e)})
        raise HTTPException(status_code=502, detail=f"Lỗi khi index: {e}")

    logger.info("rag.service.index.done", extra={
        "book_id": book_id, "pages": len(docs), "chunks": total_chunks,
    })

    return IndexResponse(
        book_id=book_id,
        title=book.title,
        total_pages=len(docs),
        total_chunks=total_chunks,
        message=f"Đã index {len(docs)} trang → {total_chunks} chunks vào ChromaDB",
    )


# ── RAG summarize ──────────────────────────────────────────────────────────────

async def rag_summarize(book_id: int, db: Session) -> RagSummarizeResponse:
    """Bài 153 — RAG Retrieval Execution: tóm tắt dựa trên nội dung thật của sách.

    Khác với summarize thường (dùng title/description):
    → Lấy chunks quan trọng nhất → LLM tóm tắt từ nội dung gốc.
    """
    _check_indexed(book_id)

    repo = BookRepository(db)
    book = repo.get_by_id(book_id)

    # Bài 147: Retrieve — dùng query mô tả để lấy chunks quan trọng
    retriever = vectorstore.get_retriever(book_id)
    query = f"Nội dung chính, ý nghĩa và thông điệp của cuốn sách {book.title}"
    chunks = retriever.invoke(query)

    if not chunks:
        raise HTTPException(status_code=404, detail="Không tìm thấy nội dung trong index.")

    # Build context từ chunks
    context = _build_context(chunks)

    # LLM generate
    from app.ai import tasks
    prompt = _build_rag_summarize_prompt(book.title, book.author.name, context)

    try:
        summary = await tasks._call_chat(prompt, max_tokens=settings.rag_max_tokens_summarize)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM lỗi: {e}")

    logger.info("rag.service.summarize.done", extra={"book_id": book_id, "chunks_used": len(chunks)})

    return RagSummarizeResponse(
        book_id=book_id,
        title=book.title,
        summary=summary,
        chunks_used=len(chunks),
        source_pages=sorted({c.metadata.get("page", 0) + 1 for c in chunks}),
    )


# ── RAG Q&A ───────────────────────────────────────────────────────────────────

async def ask_book(book_id: int, question: str, db: Session) -> AskResponse:
    """Bài 153 — RAG Q&A: hỏi bất kỳ câu gì về nội dung sách.

    Naive approach (bài 145): gửi cả sách vào prompt → không thực tế.
    RAG: chỉ retrieve đúng chunks liên quan → trả lời chính xác, ít token hơn.
    """
    _check_indexed(book_id)

    repo = BookRepository(db)
    book = repo.get_by_id(book_id)

    # Bài 147: Retrieve chunks liên quan nhất với câu hỏi
    retriever = vectorstore.get_retriever(book_id)
    chunks = retriever.invoke(question)

    if not chunks:
        raise HTTPException(status_code=404, detail="Không tìm thấy nội dung liên quan.")

    context = _build_context(chunks)
    prompt = _build_rag_qa_prompt(book.title, question, context)

    from app.ai import tasks
    try:
        answer = await tasks._call_chat(prompt, max_tokens=settings.rag_max_tokens_qa)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM lỗi: {e}")

    logger.info("rag.service.ask.done", extra={"book_id": book_id, "question": question[:80]})

    return AskResponse(
        book_id=book_id,
        title=book.title,
        question=question,
        answer=answer,
        chunks_used=len(chunks),
        source_pages=sorted({c.metadata.get("page", 0) + 1 for c in chunks}),
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _check_indexed(book_id: int) -> None:
    if not vectorstore.collection_exists(book_id):
        raise HTTPException(
            status_code=422,
            detail=f"Book {book_id} chưa được index. Chạy POST /ai/rag/books/{book_id}/index trước.",
        )


def _build_context(chunks) -> str:
    """Ghép chunks thành context string, kèm số trang để cite nguồn."""
    parts = []
    for chunk in chunks:
        page = chunk.metadata.get("page", 0) + 1
        parts.append(f"[Trang {page}]\n{chunk.page_content}")
    return "\n\n---\n\n".join(parts)


def _build_rag_summarize_prompt(title: str, author: str, context: str) -> str:
    return f"""Bạn là chuyên gia phân tích sách. Dựa CHÍNH XÁC vào các đoạn trích dưới đây từ cuốn "{title}" của {author}, hãy viết tóm tắt 3-5 câu bằng tiếng Việt.

Chỉ dùng thông tin từ các đoạn trích — không thêm kiến thức bên ngoài.

Nội dung trích từ sách:
{context}

Tóm tắt:"""


def _build_rag_qa_prompt(title: str, question: str, context: str) -> str:
    return f"""Dựa CHÍNH XÁC vào các đoạn trích từ cuốn "{title}" dưới đây, hãy trả lời câu hỏi bằng tiếng Việt.
Nếu không tìm thấy thông tin trong đoạn trích, hãy nói rõ "Không tìm thấy thông tin này trong sách."

Câu hỏi: {question}

Nội dung trích từ sách:
{context}

Trả lời:"""
