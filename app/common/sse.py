"""SSE helpers — format bytes đúng chuẩn Server-Sent Events.

Format chuẩn:
  data: {payload}\n\n     ← mỗi event một dòng, kết thúc bằng \n\n
  data: [DONE]\n\n         ← signal stream kết thúc

Browser/client parse từng \n\n là một event hoàn chỉnh.
"""
from __future__ import annotations

import json


def sse_line(data: dict | str) -> bytes:
    """Format một SSE data event.

    Dùng cho token content:
      sse_line({"choices": [{"delta": {"content": "Hello"}}]})
      → b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n'
    """
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"data: {payload}\n\n".encode()


def sse_event(event_type: str, data: dict) -> bytes:
    """Format một typed SSE event (status, sources, ...).

    Dùng cho metadata events:
      sse_event("status", {"action": "tool_start", "tool": "search_books"})
      → b'data: {"type": "status", "data": {"action": "tool_start", ...}}\n\n'
    """
    return sse_line({"type": event_type, "data": data})


def sse_done() -> bytes:
    """Signal kết thúc stream."""
    return b"data: [DONE]\n\n"
