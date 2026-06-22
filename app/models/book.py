from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base import Base


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    published_year = Column(Integer, nullable=True)
    author_id = Column(Integer, ForeignKey("authors.id", ondelete="RESTRICT"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False)

    # Bài 108: Lưu vector embedding dưới dạng JSON string trong SQLite.
    # SQLite không có kiểu vector native → dùng Text, serialize/deserialize bằng json.
    # Production với PostgreSQL → dùng pgvector extension (kiểu VECTOR(1536)).
    embedding = Column(Text, nullable=True)

    author = relationship("Author", back_populates="books")
    category = relationship("Category", back_populates="books")
