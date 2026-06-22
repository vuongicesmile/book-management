"""Raw API calls tới OpenAI — tầng thấp nhất, không có business logic.

Đây là nơi DUY NHẤT gọi HTTP tới OpenAI. service.py không gọi trực tiếp.
Mọi giá trị cấu hình (URL, timeout, model, temperature) lấy từ settings — không hardcode.
"""
from __future__ import annotations

import json
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class AINotConfiguredError(Exception):
    """Raise khi openai_api_key chưa được set trong .env."""


def _check_api_key() -> None:
    if not settings.openai_api_key:
        raise AINotConfiguredError(
            "OPENAI_API_KEY chưa được cấu hình. Thêm vào .env: OPENAI_API_KEY=sk-..."
        )


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.openai_api_key}"}


async def _call_chat(
    prompt: str,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    """Gọi chat/completions, trả về text.

    max_tokens  — default: settings.openai_max_tokens_default
    temperature — default: settings.openai_temperature_default
    """
    _check_api_key()
    _max_tokens = max_tokens if max_tokens is not None else settings.openai_max_tokens_default
    _temperature = temperature if temperature is not None else settings.openai_temperature_default

    logger.info("ai.tasks.chat_call", extra={"model": settings.openai_chat_model, "max_tokens": _max_tokens})

    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.openai_chat_completions_url,  # từ config, không hardcode
            headers=_auth_headers(),
            json={
                "model": settings.openai_chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": _max_tokens,
                "temperature": _temperature,
            },
            timeout=settings.openai_chat_timeout,  # từ config
        )
        response.raise_for_status()

    data = response.json()
    logger.info("ai.tasks.chat_done", extra={"tokens_used": data.get("usage", {}).get("total_tokens")})
    return data["choices"][0]["message"]["content"].strip()


async def _call_chat_json(
    prompt: str,
    max_tokens: int | None = None,
) -> dict:
    """Tier 2: json_object mode — đảm bảo output parse được.

    Prompt PHẢI chứa chữ "JSON" — OpenAI enforce điều này.
    temperature lấy từ settings.openai_temperature_json (default 0.2).
    """
    _check_api_key()
    _max_tokens = max_tokens if max_tokens is not None else settings.openai_max_tokens_default

    logger.info("ai.tasks.json_call", extra={"model": settings.openai_chat_model, "max_tokens": _max_tokens})

    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.openai_chat_completions_url,
            headers=_auth_headers(),
            json={
                "model": settings.openai_chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "max_tokens": _max_tokens,
                "temperature": settings.openai_temperature_json,
            },
            timeout=settings.openai_chat_timeout,
        )
        response.raise_for_status()

    data = response.json()
    logger.info("ai.tasks.json_done", extra={"tokens_used": data.get("usage", {}).get("total_tokens")})
    return json.loads(data["choices"][0]["message"]["content"])


async def _call_chat_schema(
    prompt: str,
    schema: dict,
    max_tokens: int | None = None,
) -> dict:
    """Tier 3: json_schema strict — output bắt buộc đúng schema.

    temperature lấy từ settings.openai_temperature_schema (default 0.0).
    Luôn check finish_reason == "refusal" — model có thể từ chối.
    """
    _check_api_key()
    _max_tokens = max_tokens if max_tokens is not None else settings.openai_max_tokens_default

    logger.info("ai.tasks.schema_call", extra={"model": settings.openai_chat_model})

    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.openai_chat_completions_url,
            headers=_auth_headers(),
            json={
                "model": settings.openai_chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": schema,
                "max_tokens": _max_tokens,
                "temperature": settings.openai_temperature_schema,
            },
            timeout=settings.openai_chat_timeout,
        )
        response.raise_for_status()

    data = response.json()
    choice = data["choices"][0]

    if choice.get("finish_reason") == "refusal":
        raise ValueError(f"Model từ chối: {choice['message'].get('refusal')}")

    logger.info("ai.tasks.schema_done", extra={"tokens_used": data.get("usage", {}).get("total_tokens")})
    return json.loads(choice["message"]["content"])


async def _call_embedding(text: str) -> list[float]:
    """Gọi embeddings, trả về vector list[float] 1536 chiều."""
    _check_api_key()

    logger.info("ai.tasks.embedding_call", extra={"model": settings.openai_embedding_model, "text_len": len(text)})

    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.openai_embeddings_url,          # từ config
            headers=_auth_headers(),
            json={
                "model": settings.openai_embedding_model,
                "input": text,
            },
            timeout=settings.openai_embedding_timeout,  # từ config, tách riêng với chat
        )
        response.raise_for_status()

    data = response.json()
    embedding = data["data"][0]["embedding"]

    logger.info("ai.tasks.embedding_done", extra={"dimensions": len(embedding)})
    return embedding


def pydantic_to_openai_schema(model_class: type, name: str) -> dict:
    """Tạo OpenAI json_schema response_format từ Pydantic model.

    Ví dụ:
        schema = pydantic_to_openai_schema(BookAnalysis, "book_analysis")
        result = await _call_chat_schema(prompt, schema)
        book = BookAnalysis.model_validate(result)
    """
    raw = model_class.model_json_schema()
    _add_additional_properties_false(raw)
    return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": raw}}


def _add_additional_properties_false(schema: dict) -> None:
    """Đệ quy thêm additionalProperties: false — bắt buộc cho strict mode."""
    if schema.get("type") == "object":
        schema["additionalProperties"] = False
    for value in schema.get("properties", {}).values():
        _add_additional_properties_false(value)
    for item in schema.get("anyOf", []) + schema.get("allOf", []):
        _add_additional_properties_false(item)
