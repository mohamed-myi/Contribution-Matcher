"""
Redis-backed rate limiter for authentication endpoints.

Provides:
- Per-IP rate limiting
- Configurable windows and limits
- Automatic expiry
"""

import time
from dataclasses import dataclass
from typing import Optional, Tuple
from functools import lru_cache

from core.logging import get_logger
from core.cache import cache

logger = get_logger("security.rate_limiter")


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining: int
    limit: int
    reset_at: int  # Unix timestamp
    retry_after: Optional[int] = None  # Seconds until retry allowed
    
    def to_headers(self) -> dict:
        """Convert to HTTP headers."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_at),
        }
        if self.retry_after:
            headers["Retry-After"] = str(self.retry_after)
        return headers


class RateLimiter:
    """
    Redis-backed rate limiter using sliding window algorithm.
    
    Usage:
        limiter = RateLimiter()
        
        # Check if request is allowed
        result = limiter.check("auth", client_ip)
        if not result.allowed:
            raise TooManyRequestsError(retry_after=result.retry_after)
        
        # Record a failed attempt (for auth endpoints)
        limiter.record_failure("auth", client_ip)
    
    Configuration:
        - AUTH: 5 attempts per 5 minutes per IP
        - API: 100 requests per minute per IP (default)
    """
    
    # Rate limit configurations
    CONFIGS = {
        "auth": {
            "limit": 5,
            "window": 300,  # 5 minutes
            "key_prefix": "ratelimit:auth:",
        },
        "auth_strict": {
            "limit": 3,
            "window": 600,  # 10 minutes (for failed attempts)
            "key_prefix": "ratelimit:auth_fail:",
        },
        "api": {
            "limit": 100,
            "window": 60,  # 1 minute
            "key_prefix": "ratelimit:api:",
        },
        "discovery": {
            "limit": 10,
            "window": 60,  # 1 minute
            "key_prefix": "ratelimit:discovery:",
        },
        "export": {
            "limit": 5,
            "window": 300,  # 5 minutes
            "key_prefix": "ratelimit:export:",
        },
    }
    
    def __init__(self):
        self._available = False
    
    def initialize(self) -> bool:
        """Initialize rate limiter (checks Redis availability)."""
        cache.initialize()
        self._available = cache.is_available
        if self._available:
            logger.info("rate_limiter_initialized")
        else:
            logger.warning("rate_limiter_disabled", reason="Redis unavailable")
        return self._available
    
    @property
    def is_available(self) -> bool:
        """Check if rate limiting is available."""
        if not self._available:
            cache.initialize()
            self._available = cache.is_available
        return self._available
    
    def _get_config(self, endpoint: str) -> dict:
        """Get rate limit config for an endpoint."""
        return self.CONFIGS.get(endpoint, self.CONFIGS["api"])
    
    def _get_key(self, endpoint: str, identifier: str) -> str:
        """Generate cache key for rate limiting."""
        config = self._get_config(endpoint)
        return f"{config['key_prefix']}{identifier}"
    
    def check(
        self,
        endpoint: str,
        identifier: str,
        cost: int = 1,
    ) -> RateLimitResult:
        """
        Check if a request is allowed under rate limit.
        
        Args:
            endpoint: The endpoint type ("auth", "api", "discovery", etc.)
            identifier: Client identifier (usually IP address)
            cost: Cost of this request (default: 1)
            
        Returns:
            RateLimitResult with allowed status and limits
        """
        config = self._get_config(endpoint)
        
        # If Redis unavailable, allow the request (fail open)
        if not self.is_available:
            return RateLimitResult(
                allowed=True,
                remaining=config["limit"],
                limit=config["limit"],
                reset_at=int(time.time()) + config["window"],
            )
        
        key = self._get_key(endpoint, identifier)
        now = int(time.time())
        window_start = now - config["window"]
        
        try:
            client = cache.client
            pipe = client.pipeline()
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current entries
            pipe.zcard(key)
            
            # Get oldest entry (for reset time calculation)
            pipe.zrange(key, 0, 0, withscores=True)
            
            results = pipe.execute()
            current_count = results[1]
            oldest_entry = results[2]
            
            # Calculate reset time
            if oldest_entry:
                reset_at = int(oldest_entry[0][1]) + config["window"]
            else:
                reset_at = now + config["window"]
            
            # Check if allowed
            remaining = max(0, config["limit"] - current_count - cost)
            allowed = current_count + cost <= config["limit"]
            
            if allowed:
                # Record this request
                client.zadd(key, {f"{now}:{cost}": now})
                client.expire(key, config["window"])
                
                logger.debug(
                    "rate_limit_check",
                    endpoint=endpoint,
                    identifier=identifier[:20],  # Truncate for privacy
                    allowed=True,
                    remaining=remaining,
                )
            else:
                retry_after = reset_at - now
                
                logger.warning(
                    "rate_limit_exceeded",
                    endpoint=endpoint,
                    identifier=identifier[:20],
                    retry_after=retry_after,
                )
                
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    limit=config["limit"],
                    reset_at=reset_at,
                    retry_after=retry_after,
                )
            
            return RateLimitResult(
                allowed=True,
                remaining=remaining,
                limit=config["limit"],
                reset_at=reset_at,
            )
            
        except Exception as e:
            logger.error("rate_limit_error", error=str(e))
            # Fail open on errors
            return RateLimitResult(
                allowed=True,
                remaining=config["limit"],
                limit=config["limit"],
                reset_at=int(time.time()) + config["window"],
            )
    
    def record_failure(self, endpoint: str, identifier: str) -> None:
        """
        Record a failed authentication attempt.
        
        Uses stricter limits for failed attempts.
        
        Args:
            endpoint: Original endpoint (will use "_strict" variant)
            identifier: Client identifier
        """
        strict_endpoint = f"{endpoint}_strict"
        if strict_endpoint not in self.CONFIGS:
            strict_endpoint = endpoint
        
        if not self.is_available:
            return
        
        config = self._get_config(strict_endpoint)
        key = self._get_key(strict_endpoint, identifier)
        now = int(time.time())
        
        try:
            client = cache.client
            client.zadd(key, {f"{now}:1": now})
            client.expire(key, config["window"])
            
            logger.info(
                "auth_failure_recorded",
                identifier=identifier[:20],
            )
        except Exception as e:
            logger.error("record_failure_error", error=str(e))
    
    def reset(self, endpoint: str, identifier: str) -> None:
        """
        Reset rate limit for an identifier.
        
        Useful after successful authentication to clear failure counter.
        
        Args:
            endpoint: The endpoint type
            identifier: Client identifier
        """
        if not self.is_available:
            return
        
        key = self._get_key(endpoint, identifier)
        strict_key = self._get_key(f"{endpoint}_strict", identifier)
        
        try:
            cache.delete(key)
            cache.delete(strict_key)
            
            logger.debug(
                "rate_limit_reset",
                endpoint=endpoint,
                identifier=identifier[:20],
            )
        except Exception as e:
            logger.error("rate_limit_reset_error", error=str(e))
    
    def get_status(self, endpoint: str, identifier: str) -> RateLimitResult:
        """
        Get current rate limit status without consuming quota.
        
        Args:
            endpoint: The endpoint type
            identifier: Client identifier
            
        Returns:
            Current rate limit status
        """
        config = self._get_config(endpoint)
        
        if not self.is_available:
            return RateLimitResult(
                allowed=True,
                remaining=config["limit"],
                limit=config["limit"],
                reset_at=int(time.time()) + config["window"],
            )
        
        key = self._get_key(endpoint, identifier)
        now = int(time.time())
        window_start = now - config["window"]
        
        try:
            client = cache.client
            
            # Clean old entries and count
            client.zremrangebyscore(key, 0, window_start)
            current_count = client.zcard(key)
            oldest = client.zrange(key, 0, 0, withscores=True)
            
            if oldest:
                reset_at = int(oldest[0][1]) + config["window"]
            else:
                reset_at = now + config["window"]
            
            remaining = max(0, config["limit"] - current_count)
            
            return RateLimitResult(
                allowed=remaining > 0,
                remaining=remaining,
                limit=config["limit"],
                reset_at=reset_at,
                retry_after=reset_at - now if remaining == 0 else None,
            )
        except Exception as e:
            logger.error("get_status_error", error=str(e))
            return RateLimitResult(
                allowed=True,
                remaining=config["limit"],
                limit=config["limit"],
                reset_at=now + config["window"],
            )


# Global singleton
_rate_limiter: Optional[RateLimiter] = None


@lru_cache(maxsize=1)
def get_rate_limiter() -> RateLimiter:
    """Get the RateLimiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
        _rate_limiter.initialize()
    return _rate_limiter

