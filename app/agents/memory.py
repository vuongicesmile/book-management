"""Memory service cho BookAgent (bài 177-188 Memory Layer).

Giống vuonglearning ai_proxy/memory.py nhưng đơn giản hơn:
  - Không có vector search (plain text thay vì embedding)
  - Không có facts tầng 1 / summary tầng 2 (1 tầng đủ cho học)
  - Dùng IP làm user_id (không cần JWT auth)
  - Background rewrite sau mỗi chat giống vuonglearning

## Flow

Trước chat:
  retrieve_memory_context(user_id) → string hoặc None
  → inject vào system prompt

Sau chat:
  asyncio.create_task(update_memory_background(user_id, message, answer))
  → LLM rút ra insights → cập nhật profile
"""
from __future__ import annotations

import asyncio
import logging

from app.db.session import SessionLocal
from app.models.user_reading_profile import UserReadingProfile

logger = logging.getLogger(__name__)

# Giới hạn chiều dài memory context inject vào system prompt
# Không inject quá nhiều → tránh làm loãng system prompt
_MAX_CONTEXT_CHARS = 500


def retrieve_memory_context(user_id: str) -> str | None:
    """Fetch memory context của user để inject vào system prompt.

    Trả về None nếu user chưa có profile hoặc profile rỗng.
    Fail-open: lỗi DB → trả None, không block chat.

    Args:
        user_id: IP address hoặc session identifier

    Returns:
        String mô tả sở thích + lịch sử, hoặc None
    """
    if not user_id:
        return None

    try:
        db = SessionLocal()
        try:
            profile = db.query(UserReadingProfile).filter(
                UserReadingProfile.user_id == user_id
            ).first()
        finally:
            db.close()

        if not profile:
            return None

        parts: list[str] = []
        if profile.preferences and profile.preferences.strip():
            parts.append(f"Sở thích: {profile.preferences.strip()}")
        if profile.recent_history and profile.recent_history.strip():
            parts.append(f"Lịch sử gần đây: {profile.recent_history.strip()}")

        if not parts:
            return None

        context = "\n".join(parts)
        # Cap length — tránh inject quá nhiều vào system prompt
        if len(context) > _MAX_CONTEXT_CHARS:
            context = context[:_MAX_CONTEXT_CHARS] + "..."

        logger.info(
            "agent.memory.retrieved",
            extra={"user_id": user_id, "length": len(context)},
        )
        return context

    except Exception as exc:
        # Fail-open: memory không quan trọng hơn chat
        logger.warning("agent.memory.retrieve_error", extra={"user_id": user_id, "error": str(exc)})
        return None


async def update_memory_background(
    user_id: str,
    user_message: str,
    agent_answer: str,
) -> None:
    """Cập nhật memory profile sau khi chat kết thúc.

    Chạy như background task (asyncio.create_task) → không block response.
    Giống vuonglearning _rewrite_memory_background():
      - Đọc profile hiện tại
      - Gọi LLM để extract insights từ conversation
      - Lưu lại

    Đơn giản hơn vuonglearning: không cần optimistic concurrency vì
    single-user SQLite không có concurrent write conflicts.
    """
    if not user_id:
        return

    from app.ai.tasks import _call_chat  # lazy import, tránh circular
    from app.core.config import settings

    if not settings.openai_api_key:
        return  # không có AI → skip

    try:
        db = SessionLocal()
        try:
            profile = db.query(UserReadingProfile).filter(
                UserReadingProfile.user_id == user_id
            ).first()
            current_preferences = profile.preferences if profile else ""
            current_history = profile.recent_history if profile else ""
        finally:
            db.close()

        # Prompt yêu cầu LLM extract insights từ conversation
        prompt = f"""Bạn là hệ thống quản lý memory cho thư viện AI.

Conversation vừa xảy ra:
User: {user_message[:300]}
Agent: {agent_answer[:300]}

Profile hiện tại:
Sở thích: {current_preferences[:200] or "(chưa có)"}
Lịch sử: {current_history[:200] or "(chưa có)"}

Nhiệm vụ: Cập nhật profile dựa trên conversation trên.
Trả về JSON với 2 trường:
{{
  "preferences": "chuỗi ngắn về sở thích đọc sách (tối đa 200 chars, giữ info cũ quan trọng + thêm info mới nếu có)",
  "recent_history": "1-2 câu mô tả chủ đề vừa hỏi (tối đa 150 chars)"
}}

Chỉ trả về JSON, không giải thích thêm."""

        raw = await _call_chat(
            prompt,
            max_tokens=200,
            temperature=0.2,
        )

        # Parse JSON từ response
        import json
        import re
        # Tìm JSON block trong response
        json_match = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
        if not json_match:
            logger.warning("agent.memory.update.no_json", extra={"user_id": user_id, "raw": raw[:100]})
            return

        data = json.loads(json_match.group())
        new_preferences = str(data.get("preferences", current_preferences))[:500]
        new_history = str(data.get("recent_history", ""))[:300]

        # Lưu lại
        db = SessionLocal()
        try:
            profile = db.query(UserReadingProfile).filter(
                UserReadingProfile.user_id == user_id
            ).first()

            if profile:
                profile.preferences = new_preferences
                profile.recent_history = new_history
            else:
                profile = UserReadingProfile(
                    user_id=user_id,
                    preferences=new_preferences,
                    recent_history=new_history,
                )
                db.add(profile)

            db.commit()
            logger.info(
                "agent.memory.updated",
                extra={"user_id": user_id, "preferences_len": len(new_preferences)},
            )
        finally:
            db.close()

    except Exception as exc:
        # Fail silently — memory update không quan trọng hơn UX
        logger.warning(
            "agent.memory.update_error",
            extra={"user_id": user_id, "error": str(exc)},
        )


def save_preference_direct(user_id: str, preference: str) -> None:
    """Lưu explicit preference vào DB (gọi từ save_preference tool).

    Args:
        user_id:    IP address hoặc session identifier
        preference: Sở thích user nói rõ ràng
    """
    db = SessionLocal()
    try:
        profile = db.query(UserReadingProfile).filter(
            UserReadingProfile.user_id == user_id
        ).first()

        if profile:
            # Thêm vào preferences hiện tại, không overwrite
            existing = profile.preferences or ""
            # Tránh duplicate
            if preference.lower() not in existing.lower():
                updated = f"{existing}; {preference}".strip("; ")
                profile.preferences = updated[:500]  # hard cap
        else:
            profile = UserReadingProfile(
                user_id=user_id,
                preferences=preference[:500],
                recent_history="",
            )
            db.add(profile)

        db.commit()
        logger.info("agent.memory.preference_saved", extra={"user_id": user_id})

    finally:
        db.close()
