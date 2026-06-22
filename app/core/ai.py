"""AI client — gọi OpenAI API cho LLM và Embeddings.

Bài 102-108 áp dụng thực tế:
  - Bài 102-104: Gọi LLM để summarize / generate description
  - Bài 108:     Tạo vector embedding, tính cosine similarity
"""
from __future__ import annotations

import json
import math

import httpx

from app.core.config import settings


class AINotConfiguredError(Exception):
    """Raise khi OPENAI_API_KEY chưa được set."""
    pass


def _check_api_key() -> None:
    if not settings.OPENAI_API_KEY:
        raise AINotConfiguredError(
            "OPENAI_API_KEY chưa được cấu hình. "
            "Thêm vào file .env: OPENAI_API_KEY=sk-..."
        )


# ── LLM: Summarize & Generate ─────────────────────────────────────────────────
# Bài 102-104: Gọi LLM API, nhận text response


async def summarize_book(title: str, description: str | None, author: str) -> str:
    """Dùng LLM tóm tắt book thành 2-3 câu.

    Bài 104 — Inference: gửi prompt → LLM predict tokens → nhận text.
    Đây là non-streaming call (task completion, không cần stream).
    """
    _check_api_key()

    prompt = f"""Tóm tắt cuốn sách sau trong 2-3 câu ngắn gọn bằng tiếng Việt.

Tên sách: {title}
Tác giả: {author}
Mô tả: {description or "Không có mô tả"}

Chỉ trả về phần tóm tắt, không thêm tiêu đề hay giải thích."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            json={
                "model": settings.OPENAI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.7,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


async def generate_description(title: str, author: str, category: str) -> str:
    """Dùng LLM viết description cho book chưa có mô tả.

    Bài 102: LLM không chỉ trả lời câu hỏi — có thể generate content.
    """
    _check_api_key()

    prompt = f"""Viết mô tả ngắn gọn (3-4 câu) cho cuốn sách sau bằng tiếng Việt.
Mô tả nên hấp dẫn và thông tin về nội dung sách.

Tên sách: {title}
Tác giả: {author}
Thể loại: {category}

Chỉ trả về phần mô tả, không thêm gì khác."""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            json={
                "model": settings.OPENAI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 250,
                "temperature": 0.8,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


# ── Embeddings ────────────────────────────────────────────────────────────────
# Bài 108: Text → vector, dùng để semantic search và similar books


async def get_embedding(text: str) -> list[float]:
    """Chuyển text thành vector embedding 1536 chiều.

    Bài 108: Embedding — nghĩa gần nhau → vector gần nhau trong không gian.
    Model text-embedding-3-small → vector 1536 số float.
    """
    _check_api_key()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            json={
                "model": settings.OPENAI_EMBEDDING_MODEL,
                "input": text[:8000],  # giới hạn độ dài input
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]  # list[float] 1536 phần tử


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Đo độ tương đồng giữa 2 vectors.

    Bài 108: Cosine similarity
      = 1.0  → giống hệt nhau
      = 0.0  → không liên quan
      = -1.0 → trái nghĩa

    Công thức: cos(θ) = (a·b) / (|a| × |b|)
    Dùng math thuần (không cần numpy) cho đơn giản.
    """
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def embedding_to_json(embedding: list[float]) -> str:
    """Serialize embedding → JSON string để lưu vào SQLite TEXT column."""
    return json.dumps(embedding)


def json_to_embedding(json_str: str) -> list[float]:
    """Deserialize JSON string → list[float] để tính toán."""
    return json.loads(json_str)
