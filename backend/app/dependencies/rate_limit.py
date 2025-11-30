"""
Simple in-memory rate limiter dependency.
"""

import threading
import time
from fastapi import Depends, HTTPException, Request, status

from ..auth.dependencies import get_current_user
from ..models import User


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._buckets: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.time()
        with self._lock:
            timestamps = self._buckets.get(key, [])
            timestamps = [ts for ts in timestamps if now - ts < self.window]
            if len(timestamps) >= self.limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Try again later.",
                )
            timestamps.append(now)
            self._buckets[key] = timestamps


global_rate_limiter = RateLimiter(limit=120, window_seconds=60)


def enforce_rate_limit(
    request: Request,
    user: User = Depends(get_current_user),
):
    key = f"user:{user.id}"
    global_rate_limiter.check(key)

