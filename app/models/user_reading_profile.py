"""UserReadingProfile — lưu sở thích đọc sách của user (bài 177-188 Memory Layer).

Đây là simple long-term memory: 1 row per user, plain text, không vector.
Giống vuonglearning user_memories nhưng đơn giản hơn cho mục đích học.

Dùng IP làm user_id (không cần auth trong learning project).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text

from app.db.base import Base


class UserReadingProfile(Base):
    __tablename__ = "user_reading_profiles"

    # IP address của user — dùng làm identifier đơn giản
    user_id = Column(String(64), primary_key=True, index=True)

    # Sở thích đọc sách — free text, tối đa 1000 chars
    # Ví dụ: "Thích sách tech, đặc biệt Python và AI. Không thích fiction."
    preferences = Column(Text, nullable=False, default="")

    # Lịch sử ngắn — 3-5 chủ đề gần đây
    # Ví dụ: "Tuần trước hỏi về ML. Hôm nay tìm sách Python."
    recent_history = Column(Text, nullable=False, default="")

    # Timestamp để biết memory có cũ không
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
