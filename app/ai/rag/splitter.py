"""Bài 151: LangChain Document Chunking & Splitting.

Vấn đề: 1 trang PDF có thể 3000 tokens — vượt context window của embedding model.
Giải pháp: chia thành chunks nhỏ hơn với overlap để không mất context giữa chunks.

RecursiveCharacterTextSplitter chia theo thứ tự ưu tiên:
  \\n\\n (paragraph) → \\n (line) → " " (word) → "" (char)
→ giữ nguyên ngữ nghĩa tốt hơn split cố định theo số ký tự.
"""
from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from app.core.config import settings


def split_documents(docs: list[Document]) -> list[Document]:
    """Chia list[Document] thành chunks nhỏ hơn.

    chunk_size    = settings.rag_chunk_size    (default 1000 chars)
    chunk_overlap = settings.rag_chunk_overlap (default 200 chars)

    Overlap quan trọng: nếu câu hỏi rơi vào ranh giới 2 chunks,
    overlap đảm bảo context không bị cắt đứt.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],  # ưu tiên split tại paragraph
    )
    chunks = splitter.split_documents(docs)

    # Đánh số chunk để debug dễ hơn
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i
        chunk.metadata["total_chunks"] = len(chunks)

    return chunks
