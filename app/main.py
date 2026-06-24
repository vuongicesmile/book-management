from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
  title="Book Management API",
  description="A simple API for managing books — learning project (bài 95-188+)",
  version="1.0.0",
)

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome to the Book Management API. See /docs for API, /learning for study notes."}


@app.get("/learning", response_class=HTMLResponse, tags=["Root"], include_in_schema=False)
def learning_index():
    """Index page listing all learning docs."""
    return """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8"/>
  <title>Book Management — Learning Docs</title>
  <style>
    body{background:#0d1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
         max-width:680px;margin:3rem auto;padding:0 1rem;line-height:1.6}
    h1{color:#58a6ff;font-size:1.6rem}
    p{color:#8b949e;margin-bottom:2rem}
    a{display:block;background:#161b22;border:1px solid #30363d;border-radius:8px;
      padding:.9rem 1.2rem;margin-bottom:.6rem;color:#58a6ff;text-decoration:none;
      transition:border-color .15s}
    a:hover{border-color:#58a6ff}
    .badge{display:inline-block;background:#1f3a5f;color:#58a6ff;border-radius:20px;
           padding:.1rem .55rem;font-size:.72rem;font-weight:600;margin-right:.4rem}
    .desc{color:#8b949e;font-size:.85rem;margin-top:.25rem}
  </style>
</head>
<body>
  <h1>📚 Book Management — Learning Docs</h1>
  <p>Tài liệu lý thuyết và hướng dẫn cho các bài học từ bài 95 đến 188+.</p>

  <a href="/static/docs/llm-guide-102-110.html">
    <span class="badge">Bài 102–110</span> LLM Guide — Prompting, API, Models
    <div class="desc">OpenAI API, chat completions, temperature, tokens, embedding</div>
  </a>

  <a href="/static/docs/redis-patterns.html">
    <span class="badge">Bài 154–162</span> Redis Patterns — Cache · Rate Limiting · Async Queue
    <div class="desc">3 pattern thực tế: book cache, per-IP rate limit, RQ worker</div>
  </a>

  <a href="/static/docs/agentic-architecture.html">
    <span class="badge">Bài 163</span> Agentic Architecture — Tool-Use Loop
    <div class="desc">BaseAgent, tool registry, parallel execution, BookAgent demo</div>
  </a>

  <a href="/static/docs/memory-layer.html">
    <span class="badge">Bài 177–188</span> Memory Layer in AI Agents
    <div class="desc">Short-term vs long-term, Mem0, Vector DB, UserReadingProfile</div>
  </a>

  <a href="/static/docs/mcp-architecture.html">
    <span class="badge">Bài 207–208</span> Model Context Protocol (MCP)
    <div class="desc">Architecture, Host/Client/Server, JSON-RPC, vuonglearning dev env MCP usage</div>
  </a>
</body>
</html>"""


# đăng ký các router từ các module con
from app.api.endpoints import books, authors, categories
from app.ai.router import router as ai_router

app.include_router(books.router, prefix="/books", tags=["Books"])
app.include_router(authors.router, prefix="/authors", tags=["Authors"])
app.include_router(categories.router, prefix="/categories", tags=["Categories"])
app.include_router(ai_router, prefix="/ai", tags=["AI"])

from app.ai.rag.router import router as rag_router
app.include_router(rag_router, prefix="/ai/rag", tags=["RAG"])

from app.agents.router import router as agent_router
app.include_router(agent_router, prefix="/agents", tags=["Agents"])

# Mount docs folder as static — accessible at /static/docs/*.html
# Import StaticFiles đã có sẵn ở đầu file
app.mount("/static/docs", StaticFiles(directory="docs"), name="docs")
