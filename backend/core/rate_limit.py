"""Rate limiter for protecting API endpoints from request dumping.

Supports both in-memory (single-server) and Redis (distributed) backends.
"""

import time
from collections import defaultdict
from threading import Lock
from typing import Annotated, Optional, Protocol

from fastapi import Depends, HTTPException, status, Request

from core.config import settings
from api.dependencies import get_current_user
from modules.users.models import User


class RateLimiterBackend(Protocol):
    """Protocol for rate limiter backends."""

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, float | None]:
        """Return (allowed, retry_after_seconds)."""
        ...


class InMemoryRateLimiter:
    """In-memory sliding-window rate limiter. Suitable for single-server deployments."""

    def __init__(self) -> None:
        self._timestamps: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, float | None]:
        if not settings.RATE_LIMIT_ENABLED:
            return True, None

        now = time.time()
        with self._lock:
            # Drop timestamps outside the current window.
            window_start = now - window_seconds
            self._timestamps[key] = [
                ts for ts in self._timestamps[key] if ts > window_start
            ]

            if len(self._timestamps[key]) >= max_requests:
                oldest = min(self._timestamps[key])
                retry_after = max(0.0, window_seconds - (now - oldest))
                return False, retry_after

            self._timestamps[key].append(now)
            return True, None


class RedisRateLimiter:
    """Redis-backed sliding-window rate limiter. Suitable for distributed deployments."""

    def __init__(self, redis_url: str) -> None:
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, float | None]:
        if not settings.RATE_LIMIT_ENABLED:
            return True, None

        now = time.time()
        window_start = now - window_seconds
        redis_key = f"ratelimit:{key}"

        # Use a sorted set with timestamps as scores
        pipe = self._redis.pipeline()
        # Remove old entries
        pipe.zremrangebyscore(redis_key, 0, window_start)
        # Count current entries
        pipe.zcard(redis_key)
        # Add current request
        pipe.zadd(redis_key, {str(now): now})
        # Set expiry
        pipe.expire(redis_key, window_seconds + 1)
        results = pipe.execute()

        current_count = results[1]
        if current_count >= max_requests:
            # Get oldest entry to calculate retry_after
            oldest = self._redis.zrange(redis_key, 0, 0, withscores=True)
            if oldest:
                oldest_time = oldest[0][1]
                retry_after = max(0.0, window_seconds - (now - oldest_time))
                return False, retry_after
            return False, float(window_seconds)

        return True, None


def get_rate_limiter() -> RateLimiterBackend:
    """Get the appropriate rate limiter backend based on configuration."""
    if settings.REDIS_URL:
        return RedisRateLimiter(settings.REDIS_URL)
    return InMemoryRateLimiter()


# Global rate limiter instance
_rate_limiter = get_rate_limiter()


def _client_key(request: Request, user_id: str | None) -> str:
    if user_id:
        return f"user:{user_id}"
    client = request.client
    host = client.host if client else "unknown"
    return f"ip:{host}"


def rate_limit_dependency(
    request: Request,
    user: Annotated[Optional[User], Depends(get_current_user)] = None,
) -> None:
    """FastAPI dependency that enforces per-user/IP rate limits.

    Raises HTTP 429 with a ``Retry-After`` header when the limit is exceeded.
    """
    user_id = str(user.id) if user else None
    key = _client_key(request, user_id)
    allowed, retry_after = _rate_limiter.is_allowed(
        key,
        settings.RATE_LIMIT_REQUESTS,
        settings.RATE_LIMIT_WINDOW_SECONDS,
    )
    if not allowed:
        headers = {}
        if retry_after is not None:
            headers["Retry-After"] = str(int(retry_after) + 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "You're sending requests too quickly. Please wait a moment "
                "before asking another question."
            ),
            headers=headers,
        )
