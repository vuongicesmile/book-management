from pydantic import BaseModel


class Settings(BaseModel):
    PROJECT_NAME: str = "Book management API"

    SQLALCHEMY_DATABASE_URL: str = "sqlite:///./app.db"

settings = Settings() # tạo 1 inctance của class Settings để có thể truy cập vào các biến cấu hình trong ứng dụng cho toàn appp


# ---
#   Tại sao dùng Pydantic thay vì dict thông thường?

#   # Cách thường (không an toàn)
#   config = {
#       "PROJECT_NAME": "Book API",
#       "PORT": "abc"  # sai kiểu, không ai báo lỗi
#   }

#   # Pydantic (type-safe)
#   class Settings(BaseModel):
#       PORT: int = 8000

#   Settings(PORT="abc")  # → ValidationError ngay lập tức

#   ---
#   Thực tế nên dùng pydantic-settings để đọc từ file .env:

#   from pydantic_settings import BaseSettings

#   class Settings(BaseSettings):
#       PROJECT_NAME: str = "Book management API"
#       SQLALCHEMY_DATABASE_URL: str = "sqlite:///./app.db"

#       class Config:
#           env_file = ".env"  # đọc từ .env nếu có

#   settings = Settings()

#   Lúc đó bạn có thể tạo file .env:
#   SQLALCHEMY_DATABASE_URL=postgresql://user:pass@localhos
#   t/bookdb