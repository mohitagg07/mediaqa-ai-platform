"""
rate_limiter.py
Redis-based sliding-window rate limiter.

Default limits (configurable via env):
  - 60 requests / minute  per IP   (general)
  - 20 requests / minute  per user (authenticated)
  - 10 requests / minute  per IP   for /chat and /upload (heavy endpoints)
"""

import time
import logging
from typing import Optional
import redis.asyncio as aioredis
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> Optional[aioredis.Redis]:
    """Lazy-init async Redis client; returns None if Redis is unavailable."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            await _redis_client.ping()
            logger.info("Rate-limiter: Redis connected")
        except Exception as e:
            logger.warning(f"Rate-limiter: Redis unavailable ({e}). Rate limiting disabled.")
            _redis_client = None
    return _redis_client


async def is_rate_limited(
    key: str,
    max_requests: int = 60,
    window_seconds: int = 60,
) -> tuple[bool, dict]:
    """
    Sliding-window rate limiter using Redis INCR + EXPIRE.

    Returns:
        (is_limited: bool, headers: dict)  — headers to attach to response.
    """
    redis = await get_redis()
    if redis is None:
        # Redis down → fail open (allow all requests)
        return False, {}

    try:
        pipe = redis.pipeline()
        now_window = int(time.time() // window_seconds)
        redis_key = f"rl:{key}:{now_window}"

        pipe.incr(redis_key)
        pipe.expire(redis_key, window_seconds * 2)
        results = await pipe.execute()

        count = results[0]
        remaining = max(0, max_requests - count)
        reset_at = (now_window + 1) * window_seconds

        headers = {
            "X-RateLimit-Limit": str(max_requests),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_at),
        }

        if count > max_requests:
            logger.warning(f"Rate limit exceeded for key: {key} ({count}/{max_requests})")
            return True, headers

        return False, headers

    except Exception as e:
        logger.error(f"Rate limiter error: {e}")
        return False, {}  # fail open


async def check_rate_limit(
    identifier: str,
    endpoint_type: str = "general",
    user_id: Optional[str] = None,
) -> tuple[bool, dict]:
    """
    High-level rate limit check combining IP + user limits.

    endpoint_type: "general" | "heavy"
    Returns (is_limited, headers).
    """
    # Heavy endpoints (chat, upload) get stricter limits
    if endpoint_type == "heavy":
        ip_limit, window = 10, 60
    else:
        ip_limit, window = 60, 60

    # Check IP-based limit
    limited, headers = await is_rate_limited(
        key=f"ip:{identifier}:{endpoint_type}",
        max_requests=ip_limit,
        window_seconds=window,
    )
    if limited:
        return True, headers

    # Additional per-user limit for authenticated users
    if user_id:
        user_limit = 20 if endpoint_type == "heavy" else 120
        limited, user_headers = await is_rate_limited(
            key=f"user:{user_id}:{endpoint_type}",
            max_requests=user_limit,
            window_seconds=window,
        )
        if limited:
            return True, user_headers
        headers.update(user_headers)

    return False, headers


async def close_redis():
    """Close Redis connection on shutdown."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Rate-limiter: Redis connection closed")
