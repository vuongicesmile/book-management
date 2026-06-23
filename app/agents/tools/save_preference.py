"""Tool: save_preference — lưu sở thích đọc sách vào long-term memory.

Giống vuonglearning save_memory_tool.py (remember_this tool):
  - User nói "nhớ rằng tôi thích sách..." → LLM gọi tool này
  - Tool lưu vào DB → persist cross-session
  - Lần sau chat, memory được inject vào system prompt

Khác biệt:
  - Không có health data filter (không cần cho sách)
  - Dùng user_id từ ToolContext thay vì gọi internal API
"""
from __future__ import annotations

import logging

from app.agents.tools.registry import register_tool

logger = logging.getLogger(__name__)


@register_tool(
    name="save_preference",
    description=(
        "Lưu sở thích đọc sách của người dùng vào bộ nhớ dài hạn. "
        "Gọi khi người dùng nói 'nhớ rằng tôi thích...', 'tôi không thích...', "
        "'lưu lại sở thích của tôi là...'. "
        "Không gọi tự động — chỉ khi user ra lệnh rõ ràng."
    ),
    parameters={
        "type": "object",
        "properties": {
            "preference": {
                "type": "string",
                "description": (
                    "Mô tả sở thích dưới dạng câu ngắn gọn. "
                    "Ví dụ: 'Thích sách về AI và machine learning', "
                    "'Không thích sách tiếng Anh', 'Ưu tiên sách có ví dụ thực tế'"
                ),
            },
            "user_id": {
                "type": "string",
                "description": "ID người dùng (tự điền từ context, không hỏi user)",
            },
        },
        "required": ["preference", "user_id"],
    },
)
async def save_preference(preference: str, user_id: str) -> str:
    """Lưu preference vào UserReadingProfile.

    Args:
        preference: Sở thích cần lưu
        user_id:    Identifier của user (IP hoặc session ID)

    Returns:
        Confirmation message cho LLM đọc
    """
    from app.agents.memory import save_preference_direct

    if not preference or not preference.strip():
        return "Không có sở thích để lưu."

    if not user_id:
        return "Không xác định được user, không thể lưu."

    save_preference_direct(user_id, preference.strip())
    logger.info("tool.save_preference.done", extra={"user_id": user_id})
    return f"Đã lưu sở thích: {preference.strip()}"
