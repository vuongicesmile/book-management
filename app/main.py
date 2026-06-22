from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(
  title="Book management API",
  description="A simple API for managing books in a library",
  version="1.0.0",
)

@app.get("/") #127.0.0.1:8000
def read_root():
    return {"message": "Welcome to the Book management API"}


# đăng ký các router từ các module con
from app.api.endpoints import books, authors, categories, ai

app.include_router(books.router, prefix="/books", tags=["Books"])
app.include_router(authors.router, prefix="/authors", tags=["Authors"])
app.include_router(categories.router, prefix="/categories", tags=["Categories"])
app.include_router(ai.router, prefix="/ai", tags=["AI"])