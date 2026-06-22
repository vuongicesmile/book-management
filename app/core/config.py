"""Config dùng pydantic-settings — đọc từ .env tự động.

Bài 100 Best Practice: config tập trung, không hardcode giá trị trong code.
pydantic-settings = pydantic + đọc env vars / .env file.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Book Management API"
    SQLALCHEMY_DATABASE_URL: str = "sqlite:///./app.db"

    # OpenAI API key — đọc từ env var OPENAI_API_KEY hoặc file .env
    # Nếu không set → AI features trả về lỗi rõ ràng thay vì crash
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
