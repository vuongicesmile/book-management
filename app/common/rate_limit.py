"""Rate limiting dùng Redis — học từ pattern vuonglearning.

Pattern vuonglearning (services/vuonglearning-api/src/common/rate_limit.py):
  - Lua script atomic INCR + EXPIRE (không bị race condition)
  - Per-route limits (signin=10, default=220)
  - Fail-open khi Redis down

Book-management version: áp dụng cho AI endpoints để bảo vệ OpenAI quota.

Tại sao Lua?
  INCR rồi EXPIRE là 2 lệnh Redis riêng → có thể bị race condition:
    Process A: INCR key → 1
    Process B: INCR key → 2
    Process A: EXPIRE key 60  ← set TTL
    Process B: EXPIRE key 60  ← ghi đè TTL = reset window!
  Lua chạy atomically → 2 lệnh như 1 → không race condition.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, Request

from app.common.redis import get_redis
from app.core.config import settings

logger = logging.getLogger(__name__)

# Atomic: INCR counter, set EXPIRE chỉ lần đầu (khi counter == 1)
# Học trực tiếp từ vuonglearning rate_limit.py:88
_RATE_LIMIT_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


async def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    """Increment counter tại key. Raise HTTP 429 nếu vượt max_requests.

    key           — unique per (user/IP + endpoint), VD: "bm:rl:ai:192.168.1.1"
    max_requests  — ngưỡng tối đa trong window
    window_seconds — độ dài window tính bằng giây
    """
    try:
        r = get_redis()
        current = await r.eval(_RATE_LIMIT_LUA, 1, key, window_seconds)  # type: ignore[misc]
        if current > max_requests:
            logger.warning("rate_limit.exceeded", extra={"key": key, "count": current})
            raise HTTPException(
                status_code=429,
                detail=f"Quá nhiều request. Tối đa {max_requests} lần / {window_seconds}s.",
            )
    except HTTPException:
        raise
    except Exception:
        # Fail-open: nếu Redis down → cho qua, không block user
        logger.warning("rate_limit.redis_error", extra={"key": key})


async def check_ai_rate_limit(request: Request) -> None:
    """Rate limit cho AI endpoints — protect OpenAI cost.

    Dùng IP của client làm key.
    Limit từ settings: rate_limit_ai_max / rate_limit_ai_window
    """
    ip = request.client.host if request.client else "unknown"
    key = f"bm:rl:ai:{ip}"
    await check_rate_limit(key, settings.rate_limit_ai_max, settings.rate_limit_ai_window)
