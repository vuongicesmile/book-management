"""Unified config via pydantic-settings — học từ pattern production.

Pattern chính:
  1. SettingsConfigDict (pydantic-settings v2) thay cho class Config lồng
  2. @lru_cache get_settings() — singleton, không tạo object mới mỗi lần import
  3. Mọi giá trị có thể thay đổi theo môi trường ĐỀU là field — không hardcode
  4. Group theo sections với comment rõ ràng
  5. @property cho giá trị tính từ fields khác

Cách đọc ưu tiên (pydantic-settings):
  1. Env var (VD: export OPENAI_API_KEY=sk-...)   ← production/docker
  2. File .env trong thư mục chạy                 ← local dev
  3. Default value trong class                    ← fallback
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # SettingsConfigDict = cách khai báo config mới (pydantic-settings v2)
    # Thay thế cho "class Config" lồng bên trong — cú pháp cũ, deprecated
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ──────────────────────────────────────────────────────────────────
    project_name: str = "Book Management API"
    env: str = "development"
    debug: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./app.db"

    # ── OpenAI — credentials ─────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"  # đổi để dùng proxy/local LLM

    # ── OpenAI — models ──────────────────────────────────────────────────────
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # ── OpenAI — timeouts (giây) ─────────────────────────────────────────────
    openai_chat_timeout: float = 30.0
    openai_embedding_timeout: float = 10.0

    # ── OpenAI — token limits per task ──────────────────────────────────────
    openai_max_tokens_summarize: int = 200
    openai_max_tokens_describe: int = 250
    openai_max_tokens_analyze: int = 150
    openai_max_tokens_default: int = 300

    # ── OpenAI — temperatures per task ──────────────────────────────────────
    # 0.0 = deterministic, 0.7 = balanced, 0.8 = creative
    openai_temperature_default: float = 0.7
    openai_temperature_creative: float = 0.8   # generate description — cần sáng tạo hơn
    openai_temperature_json: float = 0.2        # json_object mode — cần ổn định hơn
    openai_temperature_schema: float = 0.0      # json_schema strict — phải deterministic

    # ── AI — batch/search behaviour ─────────────────────────────────────────
    ai_embed_rate_limit_sleep: float = 0.1      # sleep giữa embedding calls khi batch
    ai_semantic_search_threshold: float = 0.3   # cosine similarity tối thiểu

    # ── RAG — file handling ──────────────────────────────────────────────────
    rag_upload_dir: str = "uploads"             # thư mục lưu PDF upload
    rag_chroma_dir: str = ".chroma"             # ChromaDB persistent directory

    # ── RAG — chunking (bài 151) ─────────────────────────────────────────────
    rag_chunk_size: int = 1000                  # max chars mỗi chunk
    rag_chunk_overlap: int = 200                # overlap giữa chunks liền kề

    # ── RAG — retrieval (bài 152) ────────────────────────────────────────────
    rag_retrieval_top_k: int = 4                # số chunks lấy ra khi similarity search

    # ── RAG — token limits ────────────────────────────────────────────────────
    rag_max_tokens_summarize: int = 600         # tóm tắt từ chunks — nhiều hơn title-based
    rag_max_tokens_qa: int = 500                # Q&A từ chunks

    # ── Derived properties ───────────────────────────────────────────────────

    @property
    def openai_chat_completions_url(self) -> str:
        return f"{self.openai_base_url}/chat/completions"

    @property
    def openai_embeddings_url(self) -> str:
        return f"{self.openai_base_url}/embeddings"

    @property
    def is_dev(self) -> bool:
        return self.env == "development"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.openai_api_key)


# @lru_cache: Settings object chỉ tạo 1 lần duy nhất, tái sử dụng mọi nơi
# Lợi ích: không đọc lại .env file mỗi request
@lru_cache
def get_settings() -> Settings:
    return Settings()


# Shortcut import — from app.core.config import settings
# An toàn vì lru_cache đảm bảo luôn là cùng 1 object
settings = get_settings()
