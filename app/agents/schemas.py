"""Schemas cho Agent API endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """Request body cho POST /agents/chat."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Câu hỏi hoặc yêu cầu cho agent",
        examples=["Tìm sách về Python và tóm tắt cuốn đầu tiên"],
    )


class ToolCallRecord(BaseModel):
    """Ghi lại một tool call đã được thực thi."""
    tool: str = Field(description="Tên tool đã gọi")
    args: str = Field(description="Arguments dưới dạng JSON string")


class AgentChatResponse(BaseModel):
    """Response từ agent chat endpoint."""
    answer: str = Field(description="Câu trả lời cuối cùng từ agent")
    tool_calls: list[ToolCallRecord] = Field(
        default_factory=list,
        description="Danh sách tool calls đã thực hiện trong quá trình xử lý",
    )
    iterations: int = Field(description="Số vòng LLM loop đã chạy")
