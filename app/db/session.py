# phần kết nối db với SQLAlchemy
from sqlalchemy import create_engine # tạo engine kết nối đến db
from sqlalchemy.orm import sessionmaker #factory tạo session để tương tác với db

from app.core.config import settings # import cấu hình (DB url) từ settings

engine = create_engine(
  settings.SQLALCHEMY_DATABASE_URL, 
  connect_args={"check_same_thread": False} if settings.SQLALCHEMY_DATABASE_URL.startswith("sqlite:///") else None
) # tạo engine kết nối đến db, với SQLite cần thêm connect_args


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# tạo factory session để tạo session mới khi cần
#  Giải thích:

#   ┌──────────────┬────────────────────────────────────┐
#   │              │           Dùng để làm gì           │
#   ├──────────────┼────────────────────────────────────┤
#   │ engine       │ Kết nối thực tế tới database file  │
#   │              │ app.db                             │
#   ├──────────────┼────────────────────────────────────┤
#   │ SessionLocal │ Factory — mỗi request tạo 1        │
#   │              │ session mới, dùng xong đóng lại    │
#   ├──────────────┼────────────────────────────────────┤
#   │ Base         │ Class cha cho tất cả models (bảng  │
#   │              │ trong DB)         