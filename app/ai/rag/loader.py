"""Bài 150: LangChain Document Loaders — đọc PDF thành Documents.

LangChain Document = {page_content: str, metadata: {source, page, ...}}
PyPDFLoader tự xử lý từng trang → list[Document], mỗi Document = 1 trang PDF.
"""
from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document


def load_pdf(file_path: str | Path) -> list[Document]:
    """Đọc PDF → list[Document], mỗi Document là 1 trang.

    Document.page_content = text của trang
    Document.metadata     = {"source": path, "page": 0, "total_pages": N}
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Chỉ hỗ trợ PDF, nhận được: {path.suffix}")

    loader = PyPDFLoader(str(path))
    docs = loader.load()  # trả về list[Document]

    # Thêm metadata hữu ích
    for doc in docs:
        doc.metadata["file_name"] = path.name
        doc.metadata["total_pages"] = len(docs)

    return docs
