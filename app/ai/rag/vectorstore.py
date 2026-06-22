"""Bài 148 + 152: Local Vector DB với ChromaDB — lưu và tìm chunks.

Bài 148: ChromaDB chạy local (không cần Docker) — persist_directory lưu ra disk.
Bài 152: LangChain Vector Store as Retrievers — .as_retriever() để search.

ChromaDB collection = 1 "bảng" riêng cho mỗi book.
Naming: "book_{book_id}" — tách biệt dữ liệu giữa các sách.
"""
from __future__ import annotations

import logging

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_embeddings() -> OpenAIEmbeddings:
    """LangChain OpenAIEmbeddings — wrapper dùng settings.openai_embedding_model."""
    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        openai_api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )


def _collection_name(book_id: int) -> str:
    return f"book_{book_id}"


def index_chunks(book_id: int, chunks: list[Document]) -> int:
    """Bài 146 — Indexing Workflow: embed chunks và lưu vào ChromaDB.

    Mỗi chunk được:
      1. Embed thành vector (OpenAI embeddings)
      2. Lưu vào ChromaDB collection riêng của book

    persist_directory → ChromaDB ghi ra disk, tồn tại qua restart.
    """
    embeddings = _get_embeddings()

    # Chroma.from_documents: embed + store trong 1 bước
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=_collection_name(book_id),
        persist_directory=settings.rag_chroma_dir,
    )

    logger.info("rag.index.done", extra={"book_id": book_id, "chunks": len(chunks)})
    return len(chunks)


def get_retriever(book_id: int):
    """Bài 152 — Vector Store as Retriever: tìm top-k chunks gần nhất với query.

    .as_retriever(search_kwargs={"k": N}) → trả về N chunks liên quan nhất.
    search_type="similarity" = cosine similarity mặc định của ChromaDB.
    """
    embeddings = _get_embeddings()

    vectordb = Chroma(
        collection_name=_collection_name(book_id),
        embedding_function=embeddings,
        persist_directory=settings.rag_chroma_dir,
    )

    return vectordb.as_retriever(
        search_type="similarity",
        search_kwargs={"k": settings.rag_retrieval_top_k},
    )


def collection_exists(book_id: int) -> bool:
    """Kiểm tra book đã được index chưa."""
    try:
        embeddings = _get_embeddings()
        db = Chroma(
            collection_name=_collection_name(book_id),
            embedding_function=embeddings,
            persist_directory=settings.rag_chroma_dir,
        )
        return db._collection.count() > 0
    except Exception:
        return False


def delete_index(book_id: int) -> None:
    """Xóa toàn bộ index của 1 book — dùng khi re-index."""
    embeddings = _get_embeddings()
    db = Chroma(
        collection_name=_collection_name(book_id),
        embedding_function=embeddings,
        persist_directory=settings.rag_chroma_dir,
    )
    db.delete_collection()
    logger.info("rag.index.deleted", extra={"book_id": book_id})
