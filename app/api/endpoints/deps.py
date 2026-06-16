# mỗi lần cập nhật connection trong db thì ko hợp lý, define 1 cái dùng chung
from typing import Generator

from app.db.session import Session_local

def get_db() -> Generator:
    db = Session_local # tạo 1 session mới cho mỗi request
    try:
        yield db # trả về session để sử dụng trong endpoint
    finally:
        db.close() # đảm bảo session được đóng sau khi xong việc

        Generator trong Python

  # Generator là function có thể tạm dừng và tiếp tục, dùng
  # từ khóa yield thay vì return.

  # ---
  # So sánh function thường vs generator:

  # # Function thường — chạy xong, trả về 1 lần, mất hết
  # def get_numbers():
  #     return [1, 2, 3]

  # # Generator — tạm dừng tại yield, tiếp tục khi cần
  # def get_numbers():
  #     yield 1   # dừng ở đây, trả về 1
  #     yield 2   # lần sau tiếp tục từ đây, trả về 2
  #     yield 3   # tiếp tục, trả về 3

  # gen = get_numbers()
  # next(gen)  # → 1
  # next(gen)  # → 2
  # next(gen)  # → 3
  # next(gen)  # → StopIteration

  # ---
  # Tại sao hữu ích? — Tiết kiệm bộ nhớ:

  # # Cách thường — load 1 triệu số vào RAM cùng lúc
  # def read_million():
  #     return [i for i in range(1_000_000)]  # 8MB RAM

  # # Generator — chỉ tạo 1 số mỗi lần
  # def read_million():
  #     for i in range(1_000_000):
  #         yield i  # gần 0 RAM

  # ---
  # yield trong get_db() hoạt động thế nào:

  # def get_db():
  #     db = SessionLocal()   # 1. Tạo session
  #     try:
  #         yield db           # 2. DỪNG — trả db cho 
  # endpoint dùng
  #                            #    endpoint chạy xong mới 
  # tiếp tục
  #     finally:
  #         db.close()         # 3. Tiếp tục — đóng session

  # Request vào
  #     → get_db() tạo session
  #     → yield db  ← DỪNG
  #         → endpoint nhận db, xử lý query
  #         → endpoint trả response
  #     → finally: db.close()
  # Request kết thúc

  # Nếu dùng return thay yield thì db.close() sẽ không bao 
  # giờ chạy → leak connection.

  # ---
  # Tóm tắt:

  # ┌────────┬───────────────┬────────────────────────┐
  # │        │    return     │         yield          │
  # ├────────┼───────────────┼────────────────────────┤
  # │ Chạy   │ 1 lần rồi kết │ Tạm dừng, tiếp tục     │
  # │        │  thúc         │ được                   │
  # ├────────┼───────────────┼────────────────────────┤
  # │ Bộ nhớ │ Load hết cùng │ Từng phần              │
  # │        │  lúc          │                        │
  # ├────────┼───────────────┼────────────────────────┤
  # │ Dùng   │ Giá trị đơn   │ Chuỗi giá trị /        │
  # │ cho    │               │ cleanup sau dùng       │
  # └────────┴───────────────┴────────────────────────┘
