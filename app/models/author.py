from sqlalchemy import Column, Integer, String, Text 
from sqlalchemy.orm import relationship

from app.db.base import Base
class Author(Base):
    __tablename__ = "authors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    biography = Column(Text, nullable=True)

    books = relationship("Book", back_populates="author") # thiết lập quan hệ 1-n với Book

