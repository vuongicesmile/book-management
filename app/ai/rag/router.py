"""RAG router — thin HTTP layer.

Sync endpoints:
  POST   /ai/rag/books/{id}/index           — upload PDF + index (sync, chờ kết quả)
  GET    /ai/rag/books/{id}/index/status    — kiểm tra đã index chưa
  POST   /ai/rag/books/{id}/summarize       — RAG-based tóm tắt từ nội dung thật
  POST   /ai/rag/books/{id}/ask             — hỏi bất kỳ câu hỏi về sách
  DELETE /ai/rag/books/{id}/index           — xóa index

Async endpoints (bài 154-162):
  POST   /ai/rag/books/{id}/index/async     — enqueue job, trả job_id ngay (<100ms)
  GET    /ai/rag/jobs/{job_id}              — poll job status + result
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from rq.exceptions import NoSuchJobError
from rq.job import Job, JobStatus
from sqlalchemy.orm import Session

from app.ai.rag import service, vectorstore
from app.ai.rag.schemas import (
    AskRequest,
    AskResponse,
    IndexResponse,
    IndexStatusResponse,
    RagSummarizeResponse,
)
from app.ai.rag.tasks import index_book_pdf_task
from app.api.deps import get_db
from app.core.config import settings
from app.queue import get_rag_queue, get_redis_sync
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


# ── Async endpoints (bài 154-162) ─────────────────────────────────────────────

@router.post("/books/{book_id}/index/async", status_code=202)
async def index_book_async(
    book_id: int,
    file: UploadFile = File(..., description="File PDF của sách"),
):
    """Bài 159-160: Enqueue indexing job — trả job_id ngay, không chờ.

    Tại sao async thay vì sync?
    → PDF indexing mất 30-120s → sync sẽ timeout (Nginx default 30s)
    → Async: FastAPI enqueue (<100ms) → worker làm việc → client poll

    So sánh với sync endpoint ở trên:
    → /index      : chờ đến khi xong (có thể timeout)
    → /index/async: trả job_id ngay, worker xử lý background
    """
    file_bytes = await file.read()
    q = get_rag_queue()
    job = q.enqueue(
        index_book_pdf_task,
        book_id, file_bytes, file.filename,
        job_timeout=settings.rag_job_timeout,
        result_ttl=settings.rag_result_ttl,
        description=f"Index PDF for book {book_id}",
    )
    return {
        "job_id": job.id,
        "status": "queued",
        "poll_url": f"/ai/rag/jobs/{job.id}",
        "message": f"Đã nhận file '{file.filename}', đang xử lý. Poll poll_url để biết kết quả.",
    }


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """Bài 161: Poll job status — client gọi định kỳ để check kết quả.

    Job states: queued → started → finished / failed
    """
    try:
        job = Job.fetch(job_id, connection=get_redis_sync())
    except NoSuchJobError:
        raise HTTPException(status_code=404, detail="Job không tồn tại hoặc đã hết TTL.")

    status = job.get_status()

    if status == JobStatus.FINISHED:
        return {"status": "finished", "result": job.result}

    if status == JobStatus.FAILED:
        exc = ""
        try:
            exc = str(job.latest_result().exc_string)[:300]
        except Exception:
            pass
        return {"status": "failed", "error": exc}

    # queued hoặc started
    return {
        "status": status.value,
        "enqueued_at": job.enqueued_at,
        "started_at": job.started_at,
        "description": job.description,
    }
