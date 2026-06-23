"""BookAgent — concrete agent chuyên về sách (bài 163).

## Trách nhiệm

BookAgent trả lời các câu hỏi về sách:
  - "Tìm sách về machine learning"
  - "Tóm tắt cuốn sách Python có id=5"
  - "Có sách nào về JavaScript không?"
  - "Cho tôi xem chi tiết sách id=3 rồi tóm tắt"

## Cách hoạt động (Agent loop)

User: "Tìm sách Python và tóm tắt cuốn đầu tiên"

Round 1:
  LLM thấy message + 3 tools → quyết định gọi:
    search_books(query="Python")
  Tool result: [{"id": 2, "title": "Learning Python", ...}]

Round 2:
  LLM đọc kết quả → quyết định gọi:
    summarize_book(book_id=2)
  Tool result: {"summary": "Sách dạy Python từ cơ bản..."}

Round 3:
  LLM có đủ thông tin → finish_reason="stop":
  "Tôi tìm thấy cuốn 'Learning Python'. Nội dung chính:..."

## So sánh với vuonglearning

vuonglearning ChatAgent:
  - 5300+ dòng (tools: web_search, calculator, memory, image_gen, ...)
  - Xử lý artifacts, slides, quiz, flashcard
  - Streaming SSE, Langfuse tracing
  - Memory injection, conversation history

BookAgent (học):
  - ~50 dòng
  - 3 tools: search_books, get_book, summarize_book
  - Synchronous response (không stream)
  - Đủ để hiểu pattern, không overwhelm

## Singleton pattern

get_book_agent() dùng @lru_cache — tạo một lần duy nhất tại startup.
Giống vuonglearning init_agents() khởi tạo agent singletons.
"""
from __future__ import annotations

from functools import lru_cache

from app.agents.base_agent import BaseAgent

# Import để trigger @register_tool decorators (bao gồm save_preference mới)
from app.agents.tools import get_book, save_preference, search_books, summarize_book  # noqa: F401


class BookAgent(BaseAgent):
    """Agent chuyên trả lời câu hỏi về sách trong thư viện.

    Biết 4 tools (bài 163 + 177-188):
      search_books    - tìm kiếm theo từ khóa
      get_book        - lấy chi tiết theo ID
      summarize_book  - tóm tắt nội dung bằng AI
      save_preference - lưu sở thích vào long-term memory (MỚI)
    """

    @property
    def system_prompt(self) -> str:
        return (
            "Bạn là thư viện viên AI thông minh, chuyên giúp người dùng "
            "tìm kiếm và tìm hiểu về sách.\n\n"
            "Bạn có các công cụ sau:\n"
            "1. search_books: Tìm sách theo từ khóa trong tiêu đề/mô tả\n"
            "2. get_book: Lấy thông tin chi tiết của sách theo ID\n"
            "3. summarize_book: Tóm tắt nội dung sách bằng AI\n"
            "4. save_preference: Lưu sở thích đọc sách vào bộ nhớ dài hạn\n\n"
            "Hướng dẫn:\n"
            "- Luôn dùng tool để tra cứu thông tin thực, không đoán mò\n"
            "- Nếu cần search trước rồi mới summarize, hãy làm theo thứ tự đó\n"
            "- Khi user nói 'nhớ rằng...', 'lưu lại...', hãy gọi save_preference\n"
            "- Nếu có thông tin về sở thích user (từ memory), hãy ưu tiên gợi ý phù hợp\n"
            "- Trả lời bằng tiếng Việt, thân thiện và súc tích\n"
            "- Nếu không tìm thấy sách phù hợp, hãy nói thật"
        )

    @property
    def tools(self) -> list[str]:
        return ["search_books", "get_book", "summarize_book", "save_preference"]


@lru_cache(maxsize=1)
def get_book_agent() -> BookAgent:
    """Singleton factory — tạo BookAgent một lần duy nhất.

    lru_cache(maxsize=1) đảm bảo chỉ có 1 instance trong toàn app.
    Giống vuonglearning init_agents() → _agents dict singleton.
    """
    return BookAgent()
