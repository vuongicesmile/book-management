"""Agent router — FastAPI endpoint cho BookAgent.

POST /agents/chat
  Input:  { "message": "Tìm sách Python" }
  Output: { "answer": "...", "tool_calls": [...], "iterations": 2 }

## Pattern: thin router

Router chỉ làm:
  1. Parse request
  2. Gọi agent.chat()
  3. Return response

Không có business logic trong router.
Giống vuonglearning ai_proxy/router.py → service.proxy_chat_completion()
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from app.agents.book_agent import get_book_agent
from app.agents.schemas import AgentChatRequest, AgentChatResponse, ToolCallRecord
from app.common.rate_limit import check_ai_rate_limit

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(body: AgentChatRequest, request: Request) -> AgentChatResponse:
    """Gửi câu hỏi cho BookAgent và nhận câu trả lời.

    Agent sẽ tự động:
    1. Quyết định tools cần dùng
    2. Thực thi tools (tìm DB, gọi AI)
    3. Tổng hợp kết quả thành câu trả lời

    Ví dụ:
      POST /agents/chat
      {"message": "Tìm sách về machine learning và tóm tắt cuốn đầu tiên"}

    Response:
      {
        "answer": "Tôi tìm thấy cuốn 'Hands-On ML'. Nội dung: ...",
        "tool_calls": [
          {"tool": "search_books", "args": "{\"query\": \"machine learning\"}"},
          {"tool": "summarize_book", "args": "{\"book_id\": 3}"}
        ],
        "iterations": 2
      }
    """
    # Rate limit — bảo vệ OpenAI cost (mỗi agent chat có thể gọi LLM nhiều lần)
    await check_ai_rate_limit(request)

    agent = get_book_agent()
    result = await agent.chat(body.message)

    return AgentChatResponse(
        answer=result["answer"],
        tool_calls=[ToolCallRecord(**tc) for tc in result["tool_calls"]],
        iterations=result["iterations"],
    )
