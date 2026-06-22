"""Raw API calls tới OpenAI — tầng thấp nhất.

Pattern từ ilmuchat: ai_proxy/tasks.py chứa _call_task(), generate_title(), v.v.
Đây là nơi DUY NHẤT gọi HTTP tới OpenAI API — service.py không gọi trực tiếp.

Nguyên tắc:
  - Mỗi function chỉ làm 1 việc: gọi API và trả về raw result
  - Không có business logic ở đây
  - Error handling tối giản — raise lên cho service.py xử lý
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class AINotConfiguredError(Exception):
    """Raise khi OPENAI_API_KEY chưa được set."""
    pass


def _check_api_key() -> None:
    if not settings.OPENAI_API_KEY:
        raise AINotConfiguredError(
            "OPENAI_API_KEY chưa được cấu hình. Thêm vào .env: OPENAI_API_KEY=sk-..."
        )


def _auth_headers() -> dict[str, str]:
    """Build Authorization header — giống ilmuchat's _upstream_headers()."""
    return {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}


async def _call_chat(prompt: str, max_tokens: int = 300, temperature: float = 0.7) -> str:
    """Gọi OpenAI chat/completions và trả về text response.

    Pattern từ ilmuchat: tasks.py/_call_task() gọi ai-service /task/chat/completions.
    Ở đây gọi thẳng OpenAI vì không có ai-service layer.
    """
    _check_api_key()

    logger.info("ai.tasks.chat_call", extra={"model": settings.OPENAI_MODEL, "max_tokens": max_tokens})

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=_auth_headers(),
            json={
                "model": settings.OPENAI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=30.0,
        )
        response.raise_for_status()

    data = response.json()
    result = data["choices"][0]["message"]["content"].strip()

    logger.info("ai.tasks.chat_done", extra={"tokens_used": data.get("usage", {}).get("total_tokens")})
    return result


async def _call_embedding(text: str) -> list[float]:
    """Gọi OpenAI embeddings và trả về vector list[float].

    Pattern từ ilmuchat: ai-service gọi /task/embeddings.
    text-embedding-3-small → vector 1536 chiều.
    """
    _check_api_key()

    logger.info("ai.tasks.embedding_call", extra={"model": settings.OPENAI_EMBEDDING_MODEL, "text_len": len(text)})

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers=_auth_headers(),
            json={
                "model": settings.OPENAI_EMBEDDING_MODEL,
                "input": text,
            },
            timeout=30.0,
        )
        response.raise_for_status()

    data = response.json()
    embedding = data["data"][0]["embedding"]

    logger.info("ai.tasks.embedding_done", extra={"dimensions": len(embedding)})
    return embedding
