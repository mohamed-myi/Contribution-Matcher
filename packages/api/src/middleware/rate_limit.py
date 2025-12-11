"""
Rate Limiting Middleware.

Provides centralized rate limiting using Redis.
"""

import time
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API rate limiting.
    
    Uses sliding window algorithm with Redis for distributed rate limiting.
    
    Limits are configurable per-endpoint:
    - Default: 100 requests/minute
    - Scoring endpoints: 20 requests/minute
    - Discovery endpoints: 10 requests/minute
    
    Rate limit headers:
    - X-RateLimit-Limit: Maximum requests allowed
    - X-RateLimit-Remaining: Requests remaining
    - X-RateLimit-Reset: Unix timestamp when limit resets
    - Retry-After: Seconds until limit resets (when exceeded)
    """
    
    # Endpoint-specific limits (requests per minute)
    ENDPOINT_LIMITS = {
        "/scoring/": 20,
        "/ml/train": 5,
        "/profile/import/": 10,
        "/issues/discover": 10,
    }
    
    DEFAULT_LIMIT = 100  # requests per minute
    WINDOW_SIZE = 60  # seconds
    
    def __init__(
        self,
        app,
        redis_client=None,
        default_limit: int = None,
        enabled: bool = True,
    ):
        super().__init__(app)
        self.redis_client = redis_client
        self.default_limit = default_limit or self.DEFAULT_LIMIT
        self.enabled = enabled
    
    def _get_limit_for_path(self, path: str) -> int:
        """Get the rate limit for a specific path."""
        for prefix, limit in self.ENDPOINT_LIMITS.items():
            if path.startswith(prefix):
                return limit
        return self.default_limit
    
    def _get_client_key(self, request: Request) -> str:
        """Get unique identifier for the client."""
        # Prefer authenticated user ID
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"rate_limit:user:{user_id}"
        
        # Fall back to IP address
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        return f"rate_limit:ip:{client_ip}"
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)
        
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        client_key = self._get_client_key(request)
        path_key = f"{client_key}:{request.url.path.split('/')[1]}"  # First path segment
        limit = self._get_limit_for_path(request.url.path)
        
        # Check rate limit
        is_allowed, remaining, reset_time = await self._check_rate_limit(
            path_key, limit
        )
        
        if not is_allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {limit} per minute.",
                    "retry_after": int(reset_time - time.time()),
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_time)),
                    "Retry-After": str(int(reset_time - time.time())),
                },
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(reset_time))
        
        return response
    
    async def _check_rate_limit(
        self,
        key: str,
        limit: int,
    ) -> tuple[bool, int, float]:
        """
        Check if request is within rate limit.
        
        Returns:
            Tuple of (is_allowed, remaining, reset_time)
        """
        now = time.time()
        window_start = now - self.WINDOW_SIZE
        reset_time = now + self.WINDOW_SIZE
        
        if not self.redis_client:
            # No Redis, allow all (log warning)
            return True, limit - 1, reset_time
        
        try:
            pipe = self.redis_client.pipeline()
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(now): now})
            
            # Set expiration
            pipe.expire(key, self.WINDOW_SIZE + 1)
            
            results = pipe.execute()
            current_count = results[1]  # zcard result
            
            remaining = max(0, limit - current_count - 1)
            is_allowed = current_count < limit
            
            return is_allowed, remaining, reset_time
            
        except Exception:
            # On Redis error, allow request but log
            return True, limit - 1, reset_time
