"""Raw API calls tới OpenAI — tầng thấp nhất.

Pattern từ vuonglearning: ai_proxy/tasks.py chứa _call_task(), generate_title(), v.v.
Đây là nơi DUY NHẤT gọi HTTP tới OpenAI API — service.py không gọi trực tiếp.

Nguyên tắc:
  - Mỗi function chỉ làm 1 việc: gọi API và trả về raw result
  - Không có business logic ở đây
  - Error handling tối giản — raise lên cho service.py xử lý
"""
from __future__ import annotations

import json
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
    """Build Authorization header — giống vuonglearning's _upstream_headers()."""
    return {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}


async def _call_chat(prompt: str, max_tokens: int = 300, temperature: float = 0.7) -> str:
    """Gọi OpenAI chat/completions và trả về text response.

    Pattern từ vuonglearning: tasks.py/_call_task() gọi ai-service /task/chat/completions.
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


async def _call_chat_json(
    prompt: str,
    max_tokens: int = 300,
    temperature: float = 0.2,
) -> dict:
    """Tier 2: json_object mode — đảm bảo output luôn parse được.

    Bài 119 Structured Output: prompt PHẢI chứa chữ "JSON" — OpenAI enforce.
    Trả về dict, không phải string. Dùng khi schema linh hoạt.
    """
    _check_api_key()

    logger.info("ai.tasks.json_call", extra={"model": settings.OPENAI_MODEL, "max_tokens": max_tokens})

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=_auth_headers(),
            json={
                "model": settings.OPENAI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=30.0,
        )
        response.raise_for_status()

    data = response.json()
    logger.info("ai.tasks.json_done", extra={"tokens_used": data.get("usage", {}).get("total_tokens")})
    return json.loads(data["choices"][0]["message"]["content"])


async def _call_chat_schema(
    prompt: str,
    schema: dict,
    max_tokens: int = 300,
) -> dict:
    """Tier 3: json_schema strict — output bắt buộc đúng schema, không sai được.

    Bài 119 Structured Output: dùng với pydantic_to_openai_schema() helper.
    temperature=0 vì strict schema → cần deterministic nhất.
    Luôn check finish_reason == "refusal" trước khi parse.
    """
    _check_api_key()

    logger.info("ai.tasks.schema_call", extra={"model": settings.OPENAI_MODEL})

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=_auth_headers(),
            json={
                "model": settings.OPENAI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": schema,
                "max_tokens": max_tokens,
                "temperature": 0.0,
            },
            timeout=30.0,
        )
        response.raise_for_status()

    data = response.json()
    choice = data["choices"][0]

    if choice.get("finish_reason") == "refusal":
        raise ValueError(f"Model từ chối: {choice['message'].get('refusal')}")

    logger.info("ai.tasks.schema_done", extra={"tokens_used": data.get("usage", {}).get("total_tokens")})
    return json.loads(choice["message"]["content"])


def pydantic_to_openai_schema(model_class: type, name: str) -> dict:
    """Tự động tạo OpenAI json_schema response_format từ Pydantic model.

    Dùng kết hợp với _call_chat_schema():
        schema = pydantic_to_openai_schema(BookAnalysis, "book_analysis")
        result = await _call_chat_schema(prompt, schema)
        book = BookAnalysis.model_validate(result)
    """
    schema = model_class.model_json_schema()
    _add_additional_properties_false(schema)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": schema,
        },
    }


def _add_additional_properties_false(schema: dict) -> None:
    """Đệ quy thêm additionalProperties: false — bắt buộc cho strict mode."""
    if schema.get("type") == "object":
        schema["additionalProperties"] = False
    for value in schema.get("properties", {}).values():
        _add_additional_properties_false(value)
    for item in schema.get("anyOf", []) + schema.get("allOf", []):
        _add_additional_properties_false(item)


async def _call_embedding(text: str) -> list[float]:
    """Gọi OpenAI embeddings và trả về vector list[float].

    Pattern từ vuonglearning: ai-service gọi /task/embeddings.
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
