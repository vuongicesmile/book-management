import time
import functools
import logging

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def log_duration(func):
    """Decorator — log thời gian chạy của function.

    Cách hoạt động:
        @log_duration
        def my_func(): ...

        # Python dịch thành:
        my_func = log_duration(my_func)

        # Khi gọi my_func() thực ra gọi wrapper()
        # wrapper đo thời gian → gọi func gốc → log kết quả

    @functools.wraps(func) — giữ nguyên tên/docstring của func gốc
        Không có @wraps: my_func.__name__ → "wrapper"  (sai)
        Có @wraps:       my_func.__name__ → "my_func"  (đúng)
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(f"[{func.__name__}] completed in {duration_ms:.1f}ms")
        return result
    return wrapper


def validate_pagination(max_limit: int = 500):
    """Decorator factory — nhận tham số, trả về decorator.

    Decorator thường:        @validate_pagination        (không có tham số)
    Decorator factory:       @validate_pagination(100)   (có tham số)

    Vì có tham số nên cần thêm 1 lớp wrapper:
        validate_pagination(100)  → trả về decorator
        decorator(func)           → trả về wrapper
        wrapper(*args, **kwargs)  → chạy logic thực
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            limit = kwargs.get("limit", 100)
            if limit > max_limit:
                raise HTTPException(
                    status_code=400,
                    detail=f"limit tối đa {max_limit}",
                )
            if kwargs.get("skip", 0) < 0:
                raise HTTPException(
                    status_code=400,
                    detail="skip không được âm",
                )
            return func(*args, **kwargs)
        return wrapper
    return decorator
