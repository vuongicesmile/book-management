"""Schemas cho Agent API endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """Request body cho POST /agents/chat."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Cau hoi hoac yeu cau cho agent",
        examples=["Tim sach ve Python va tom tat cuon dau tien"],
    )
    # user_id optional — neu khong co, dung IP tu request
    # Giong vuonglearning: user_id tu JWT auth, o day dung IP cho don gian
    user_id: str | None = Field(
        default=None,
        max_length=64,
        description="User identifier. Neu khong co, dung IP address lam ID.",
    )


class ToolCallRecord(BaseModel):
    """Ghi lai mot tool call da duoc thuc thi."""
    tool: str = Field(description="Ten tool da goi")
    args: str = Field(description="Arguments duoi dang JSON string")


class AgentChatResponse(BaseModel):
    """Response tu agent chat endpoint."""
    answer: str = Field(description="Cau tra loi cuoi cung tu agent")
    tool_calls: list[ToolCallRecord] = Field(
        default_factory=list,
        description="Danh sach tool calls da thuc hien trong qua trinh xu ly",
    )
    iterations: int = Field(description="So vong LLM loop da chay")
    memory_used: bool = Field(
        default=False,
        description="True neu agent co su dung memory context",
    )
