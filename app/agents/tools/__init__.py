"""Import tất cả tool modules để trigger @register_tool decorators.

Giống vuonglearning src/tools/__init__.py → discover_tools():
  - Import each tool module → decorator chạy → tool vào TOOL_REGISTRY

Khi book_agent.py import:
  from app.agents.tools import get_book, search_books, summarize_book
  → cả 3 decorators chạy → TOOL_REGISTRY có 3 entries
"""
from app.agents.tools.get_book import get_book
from app.agents.tools.search_books import search_books
from app.agents.tools.summarize_book import summarize_book

__all__ = ["search_books", "get_book", "summarize_book"]
