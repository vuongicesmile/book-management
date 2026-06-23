"""Agent router — FastAPI endpoint cho BookAgent.

POST /agents/chat
  Input:  { "message": "Tim sach Python", "user_id": "optional" }
  Output: { "answer": "...", "tool_calls": [...], "iterations": 2, "memory_used": true }

## Memory Layer (bai 177-188)

user_id duoc xac dinh theo thu tu uu tien:
  1. body.user_id — truyen tu client (e.g. session ID)
  2. request.client.host — IP address (fallback)

Memory inject: base_agent.chat(user_message, user_id) se:
  - Fetch memory context tu DB
  - Append vao system prompt
  - Background update sau khi chat xong
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from app.agents.book_agent import get_book_agent
from app.agents.memory import retrieve_memory_context
from app.agents.schemas import AgentChatRequest, AgentChatResponse, ToolCallRecord
from app.common.rate_limit import check_ai_rate_limit

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(body: AgentChatRequest, request: Request) -> AgentChatResponse:
    """Gui cau hoi cho BookAgent va nhan cau tra loi.

    Agent tu dong:
    1. Doc memory cua user (neu co) va inject vao context
    2. Quyet dinh tools can dung
    3. Thuc thi tools (tim DB, goi AI)
    4. Tong hop ket qua thanh cau tra loi
    5. Background: cap nhat memory sau chat

    Vi du:
      POST /agents/chat
      {"message": "Nho rang toi thich sach Python"}
      → Agent goi save_preference, luu vao DB

      POST /agents/chat  (lan sau)
      {"message": "Goi y sach cho toi"}
      → Agent biet "thich Python" → goi search_books("Python")
    """
    await check_ai_rate_limit(request)

    # Xac dinh user_id: body > IP fallback
    user_id: str | None = body.user_id
    if not user_id and request.client:
        user_id = request.client.host  # IP address lam fallback identifier

    # Kiem tra truoc khi chat: co memory khong?
    memory_context = retrieve_memory_context(user_id) if user_id else None

    agent = get_book_agent()
    result = await agent.chat(body.message, user_id=user_id)

    return AgentChatResponse(
        answer=result["answer"],
        tool_calls=[ToolCallRecord(**tc) for tc in result["tool_calls"]],
        iterations=result["iterations"],
        memory_used=memory_context is not None,
    )


@router.get("/memory", summary="Xem memory hien tai cua user")
async def get_memory(request: Request, user_id: str | None = None):
    """Debug endpoint: xem memory context se duoc inject cho user nay.

    Query params:
      user_id: optional — neu khong co, dung IP

    Vi du:
      GET /agents/memory
      GET /agents/memory?user_id=192.168.1.1
    """
    uid = user_id or (request.client.host if request.client else None)
    if not uid:
        return {"user_id": None, "memory": None}

    context = retrieve_memory_context(uid)
    return {
        "user_id": uid,
        "memory": context,
        "has_memory": context is not None,
    }
