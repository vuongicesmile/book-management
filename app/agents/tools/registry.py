"""Tool registry — bài 163 (Agent Architecture).

## Tại sao cần registry?

Không có registry:
  agent.py phải import từng tool thủ công → biết hết tool → khó mở rộng
  if tool_name == "search_books": result = search_books(...)
  elif tool_name == "get_book": result = get_book(...)
  ...

Có registry:
  Mỗi tool tự đăng ký bằng @register_tool
  agent.py chỉ gọi: execute_tools_parallel(tool_calls)
  Thêm tool mới không cần sửa agent.py → Open/Closed Principle

## So sánh với vuonglearning

vuonglearning dùng:
  src/tools/__init__.py  → discover_tools()  (auto-import all modules)
  src/tools/registry.py  → @register_tool decorator + execute_tools_parallel()
  src/tools/protocol.py  → ToolCall, ToolContext (typed dataclasses)

book-management dùng pattern đơn giản hơn nhưng cùng nguyên lý:
  app/agents/tools/registry.py  → @register_tool + TOOL_REGISTRY dict

## Cách dùng

  from app.agents.tools.registry import register_tool, TOOL_REGISTRY

  @register_tool(
      name="search_books",
      description="Search books by keyword",
      parameters={
          "type": "object",
          "properties": {
              "query": {"type": "string", "description": "Search keyword"}
          },
          "required": ["query"],
      },
  )
  async def search_books(query: str) -> str:
      ...
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Tool registry dict ────────────────────────────────────────────────────────
#
# Cấu trúc:
#   TOOL_REGISTRY["search_books"] = {
#       "fn":     <async function>,
#       "schema": { "type": "function", "function": { "name": ..., ...} }
#   }
#
# LLM nhận "schema" để biết cách gọi tool.
# agent nhận "fn" để thực thi khi LLM yêu cầu.
TOOL_REGISTRY: dict[str, dict[str, Any]] = {}


def register_tool(
    name: str,
    description: str,
    parameters: dict[str, Any],
):
    """Decorator đăng ký một async function vào TOOL_REGISTRY.

    Dùng như sau:
        @register_tool(name="...", description="...", parameters={...})
        async def my_tool(param1: str) -> str:
            ...

    Args:
        name:        Tên tool — phải unique, LLM dùng tên này để gọi
        description: Mô tả ngắn — LLM đọc để biết khi nào nên dùng
        parameters:  JSON Schema của input arguments
    """
    def decorator(fn):
        # Kiểm tra không đăng ký trùng tên
        if name in TOOL_REGISTRY:
            raise ValueError(f"Tool '{name}' đã được đăng ký. Dùng tên khác.")

        # Lưu vào registry
        TOOL_REGISTRY[name] = {
            "fn": fn,
            # OpenAI tool schema format
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
        }
        logger.debug("tool.registered", extra={"tool": name})
        return fn  # trả về function gốc, không wrap

    return decorator


def get_tool_schemas(names: list[str]) -> list[dict[str, Any]]:
    """Lấy danh sách OpenAI tool schemas cho một tập tool.

    Agent gọi hàm này để build request body gửi tới LLM.
    Chỉ trả về schema của tools mà agent đó hỗ trợ (không expose hết).

    Args:
        names: Danh sách tool names agent muốn enable

    Returns:
        List of OpenAI-format tool schemas
    """
    schemas = []
    for name in names:
        if name not in TOOL_REGISTRY:
            logger.warning("tool.schema_not_found", extra={"tool": name})
            continue
        schemas.append(TOOL_REGISTRY[name]["schema"])
    return schemas


async def execute_tools_parallel(
    tool_calls: list[dict[str, Any]],
    enabled_tools: list[str],
) -> list[dict[str, Any]]:
    """Thực thi nhiều tool calls song song dùng asyncio.gather.

    ## Tại sao parallel?

    LLM có thể gọi nhiều tool cùng lúc:
      "search_books(query='Python') AND get_book(id=5)"

    Nếu sequential (lần lượt):
      search_books (200ms) + get_book (50ms) = 250ms total

    Nếu parallel (cùng lúc):
      max(200ms, 50ms) = 200ms total  ← nhanh hơn

    ## So sánh với vuonglearning

    vuonglearning execute_tools_parallel():
      asyncio.gather(*[_run_one(tc, ctx) for tc in tool_calls])
      có thêm: dedup check, span tracing, metrics

    book-management: đơn giản hơn, cùng nguyên lý asyncio.gather

    Args:
        tool_calls:    List tool calls từ LLM response (đã parse JSON)
        enabled_tools: Whitelist tool names agent này cho phép

    Returns:
        List of tool result dicts (role=tool, tool_call_id, content)
    """
    async def _run_one(tc: dict[str, Any]) -> dict[str, Any]:
        tool_name = tc["function"]["name"]
        tool_call_id = tc["id"]

        # Security: chỉ cho phép tools trong whitelist
        if tool_name not in enabled_tools:
            logger.warning("tool.not_allowed", extra={"tool": tool_name})
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": f"Error: tool '{tool_name}' không được phép.",
            }

        if tool_name not in TOOL_REGISTRY:
            logger.warning("tool.not_registered", extra={"tool": tool_name})
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": f"Error: tool '{tool_name}' chưa được đăng ký.",
            }

        # Parse arguments từ JSON string
        try:
            args = json.loads(tc["function"].get("arguments", "{}"))
        except json.JSONDecodeError as e:
            logger.error("tool.args_parse_error", extra={"tool": tool_name, "error": str(e)})
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": f"Error: không parse được arguments cho '{tool_name}'.",
            }

        # Gọi tool function
        fn = TOOL_REGISTRY[tool_name]["fn"]
        try:
            logger.info("tool.execute", extra={"tool": tool_name, "args": args})
            result = await fn(**args)
            logger.info("tool.done", extra={"tool": tool_name})
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": str(result),
            }
        except Exception as exc:
            logger.error("tool.error", extra={"tool": tool_name, "error": str(exc)})
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": f"Error khi chạy '{tool_name}': {exc}",
            }

    # asyncio.gather: tất cả tools chạy song song, chờ hết rồi return
    results = await asyncio.gather(*[_run_one(tc) for tc in tool_calls])
    return list(results)
