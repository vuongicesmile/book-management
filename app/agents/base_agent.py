"""BaseAgent — lõi của agentic architecture (bài 163).

## Kiến trúc tổng quan

                   User: "Tìm sách Python và tóm tắt"
                              │
                              ▼
                       BookAgent.chat()
                              │
                    ┌─────────▼────────┐
                    │  BaseAgent       │
                    │  _tool_use_loop  │
                    └─────────┬────────┘
                              │
              ┌───────────────┼───────────────────┐
              │               │                   │
              ▼               ▼                   ▼
    [Round 1]          [Round 2]            [Round 3]
    LLM: "gọi         LLM: "gọi            LLM: "Đây là
    search_books"      summarize_book"      câu trả lời..."
         │                  │
         ▼                  ▼
  search_books()     summarize_book()
  (DB query)         (AI + cache)
         │                  │
         └──────────────────┘
              tool results
              added to messages

## So sánh với vuonglearning

vuonglearning (ai-service):
  - BaseAgent.execute() → streaming bytes (SSE)
  - tool_use_loop() trong tool_stream.py
  - Hỗ trợ partial streaming trong khi tool chạy
  - Dedup check (tránh gọi tool giống hệt nhau 2 lần)
  - Metrics + Langfuse tracing

book-management (đơn giản hơn cho học):
  - BaseAgent.chat() → trả về plain text (không stream)
  - _tool_use_loop() inline trong base class
  - Không stream — phù hợp cho REST API học tập

## Template Method Pattern

BaseAgent là abstract class — định nghĩa "thuật toán khung":
  chat():
    1. Build system prompt
    2. Gọi tool_use_loop với danh sách tools của subclass
    3. Trả về text

Subclass (BookAgent) chỉ cần override:
  - system_prompt property
  - tools property (danh sách tool names)

Phần "how to loop" nằm trong BaseAgent — không lặp code ở subclass.
"""
from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod

import httpx

from app.agents.tools.registry import execute_tools_parallel, get_tool_schemas
from app.core.config import settings

logger = logging.getLogger(__name__)

# Giới hạn số vòng lặp tool — tránh infinite loop nếu LLM kém
# vuonglearning dùng max_tool_rounds = 5 (configurable per agent)
_MAX_ITERATIONS = 8


class BaseAgent(ABC):
    """Abstract base cho tất cả agents.

    Subclasses PHẢI implement:
      - system_prompt property: string hướng dẫn agent hành xử
      - tools property: list[str] tên tools agent được phép dùng

    Subclasses CÓ THỂ override:
      - max_iterations: số vòng tool tối đa (default 8)
    """

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt hướng dẫn agent hành xử và khi nào dùng tool."""
        ...

    @property
    @abstractmethod
    def tools(self) -> list[str]:
        """Danh sách tool names agent này được phép dùng.

        Chỉ expose tools cần thiết — principle of least privilege.
        BookAgent không cần tool của GeraiAgent và ngược lại.
        """
        ...

    @property
    def max_iterations(self) -> int:
        """Số vòng tool tối đa. Override để tăng cho agent phức tạp hơn."""
        return _MAX_ITERATIONS

    async def chat(self, user_message: str, user_id: str | None = None) -> dict:
        """Entry point: nhận câu hỏi, trả về câu trả lời + lịch sử tool calls.

        ## Memory injection (bài 177-188)

        Nếu user_id được cung cấp:
          1. Fetch memory context từ DB
          2. Append vào system prompt: "Bạn biết về user: {context}"
          3. Sau chat: background task cập nhật memory

        Giống vuonglearning retrieve_memory_summary() + inject vào system prompt
        trong ai_proxy/service.py trước khi gọi ai-service.

        Args:
            user_message: Câu hỏi hoặc yêu cầu từ người dùng
            user_id:      IP hoặc session ID để fetch/update memory

        Returns:
            dict với:
              answer:     Text trả lời cuối cùng
              tool_calls: Danh sách tool calls đã thực hiện (for debugging)
              iterations: Số vòng loop đã chạy
        """
        if not settings.openai_api_key:
            return {
                "answer": "AI chưa được cấu hình. Thêm OPENAI_API_KEY vào .env",
                "tool_calls": [],
                "iterations": 0,
            }

        # ── Build system prompt với memory injection ──────────────────────
        # Bước 1: Lấy base system prompt từ subclass
        system_content = self.system_prompt

        # Bước 2: Inject user_id để tool save_preference biết dùng
        # LLM cần biết user_id cụ thể để điền vào tham số của save_preference tool
        if user_id:
            system_content += f"\n\nUser ID hiện tại: {user_id}"

        # Bước 3: Inject memory context nếu có
        # Giống vuonglearning: "User memory: {summary}" thêm vào cuối system prompt
        if user_id:
            from app.agents.memory import retrieve_memory_context
            memory_context = retrieve_memory_context(user_id)
            if memory_context:
                system_content += (
                    f"\n\nThông tin về người dùng này (từ lịch sử trước):\n{memory_context}"
                )
                logger.info(
                    "agent.chat.memory_injected",
                    extra={"user_id": user_id, "memory_len": len(memory_context)},
                )

        # Khởi tạo conversation messages
        messages: list[dict] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_message},
        ]

        # Lấy tool schemas để gửi cho LLM
        tool_schemas = get_tool_schemas(self.tools)

        logger.info(
            "agent.chat.start",
            extra={
                "agent": self.__class__.__name__,
                "tools": self.tools,
                "user_id": user_id or "anonymous",
                "message": user_message[:100],
            },
        )

        # Chạy vòng lặp tool-use
        answer, tool_history, iterations = await self._tool_use_loop(
            messages, tool_schemas
        )

        # ── Background memory update ──────────────────────────────────────
        # Sau khi chat xong → background task cập nhật memory profile
        # asyncio.create_task = fire-and-forget, không block response
        # Giống vuonglearning _rewrite_memory_background()
        if user_id and answer:
            from app.agents.memory import update_memory_background
            asyncio.create_task(
                update_memory_background(user_id, user_message, answer)
            )

        logger.info(
            "agent.chat.done",
            extra={
                "agent": self.__class__.__name__,
                "iterations": iterations,
                "tools_called": len(tool_history),
            },
        )

        return {
            "answer": answer,
            "tool_calls": tool_history,
            "iterations": iterations,
        }

    async def _tool_use_loop(
        self,
        messages: list[dict],
        tool_schemas: list[dict],
    ) -> tuple[str, list[dict], int]:
        """Vòng lặp tool-use — lõi của agentic architecture.

        ## Thuật toán

        Iteration 1:
          messages = [system, user]
          → LLM: "Tôi cần search_books(query='Python')"
          → execute search_books → kết quả: [...]
          → append assistant + tool result vào messages

        Iteration 2:
          messages = [system, user, assistant(tool_calls), tool_result]
          → LLM: "Tôi cần summarize_book(book_id=3)"
          → execute summarize_book → kết quả: "Sách nói về..."
          → append assistant + tool result vào messages

        Iteration 3:
          messages = [..., assistant2(tool_calls2), tool_result2]
          → LLM: "Dựa trên kết quả trên, đây là câu trả lời..."
          → finish_reason == "stop" → return content

        ## Tại sao loop thay vì recursion?

        Recursion: khó control depth, stack overflow với nhiều tool rounds
        Loop: explicit iteration counter → dễ debug, dễ giới hạn

        ## finish_reason

        OpenAI trả về hai giá trị quan trọng:
          "stop"       → LLM đã có câu trả lời, không cần tool nữa
          "tool_calls" → LLM muốn gọi thêm tool, continue loop

        Args:
            messages:     Conversation history (mutated in-place)
            tool_schemas: OpenAI tool definitions để LLM biết tools nào có

        Returns:
            tuple: (answer_text, tool_call_history, iteration_count)
        """
        tool_history: list[dict] = []
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            logger.debug("agent.loop.iteration", extra={"iteration": iteration})

            # ── Gọi LLM ───────────────────────────────────────────────────────
            response_data = await self._call_llm(messages, tool_schemas)
            choice = response_data["choices"][0]
            finish_reason = choice["finish_reason"]
            assistant_message = choice["message"]

            # ── Case 1: LLM trả lời xong, không cần tool ──────────────────────
            if finish_reason == "stop":
                answer = assistant_message.get("content") or ""
                logger.info("agent.loop.stop", extra={"iteration": iteration})
                return answer, tool_history, iteration

            # ── Case 2: LLM muốn gọi tool ──────────────────────────────────────
            if finish_reason == "tool_calls":
                tool_calls = assistant_message.get("tool_calls", [])

                # Bước 2a: Lưu assistant message vào history
                # QUAN TRỌNG: phải giữ nguyên assistant message có tool_calls
                # LLM cần đọc lại "tôi đã quyết định gọi tool gì" ở vòng sau
                messages.append(assistant_message)

                # Bước 2b: Log tool calls để debug
                for tc in tool_calls:
                    tc_name = tc["function"]["name"]
                    tc_args = tc["function"].get("arguments", "{}")
                    logger.info(
                        "agent.tool_call",
                        extra={"tool": tc_name, "args": tc_args[:200]},
                    )
                    tool_history.append({"tool": tc_name, "args": tc_args})

                # Bước 2c: Thực thi tất cả tools song song
                # asyncio.gather → search_books + get_book chạy cùng lúc
                tool_results = await execute_tools_parallel(
                    tool_calls, self.tools
                )

                # Bước 2d: Append tool results vào messages
                # Format: {"role": "tool", "tool_call_id": ..., "content": ...}
                # OpenAI yêu cầu phải match tool_call_id với assistant message
                messages.extend(tool_results)

                # Bước 2e: Continue loop — LLM đọc tool results và quyết định tiếp
                continue

            # ── Case 3: Unexpected finish_reason ──────────────────────────────
            logger.warning(
                "agent.loop.unexpected_finish",
                extra={"finish_reason": finish_reason, "iteration": iteration},
            )
            answer = assistant_message.get("content") or "(không có câu trả lời)"
            return answer, tool_history, iteration

        # ── Max iterations reached ─────────────────────────────────────────────
        # Vòng lặp chạy quá nhiều lần — có thể LLM đang loop tool calls
        # Lấy content của message cuối cùng nếu có
        last_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                last_content = msg["content"]
                break

        logger.warning(
            "agent.loop.max_iterations",
            extra={"max": self.max_iterations, "agent": self.__class__.__name__},
        )
        return last_content or "Đã vượt quá số vòng lặp tối đa.", tool_history, iteration

    async def _call_llm(
        self,
        messages: list[dict],
        tool_schemas: list[dict],
    ) -> dict:
        """Gọi OpenAI chat/completions API với tool_schemas.

        Dùng httpx (cùng pattern với app/ai/tasks.py) thay vì openai SDK
        để nhất quán với codebase.

        Args:
            messages:     Conversation history
            tool_schemas: OpenAI tool definitions

        Returns:
            OpenAI API response dict
        """
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

        body: dict = {
            "model": settings.openai_chat_model,
            "messages": messages,
        }

        # Chỉ thêm tools nếu có — tránh gửi empty list làm LLM confused
        if tool_schemas:
            body["tools"] = tool_schemas
            body["tool_choice"] = "auto"  # LLM tự quyết định khi nào dùng tool

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                settings.openai_chat_completions_url,
                headers=headers,
                json=body,
                timeout=60.0,  # agent có thể cần nhiều tool rounds → timeout dài hơn
            )

        if resp.status_code != 200:
            logger.error(
                "agent.llm_call_error",
                extra={"status": resp.status_code, "body": resp.text[:200]},
            )
            raise RuntimeError(f"LLM API error {resp.status_code}: {resp.text[:200]}")

        return resp.json()
