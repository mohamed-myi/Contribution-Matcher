"""
Redis-backed rate limiter for authentication endpoints.

Provides:
- Per-IP rate limiting
- Configurable windows and limits
- Automatic expiry
- In-memory fallback when Redis is unavailable (fails closed, not open)
"""

import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from functools import lru_cache

from core.logging import get_logger
from core.cache import cache

logger = get_logger("security.rate_limiter")


# =============================================================================
# In-Memory Fallback Rate Limiter
# =============================================================================

class InMemoryRateLimiter:
    """
    Simple in-memory rate limiter used as fallback when Redis is unavailable.
    
    This ensures the application fails CLOSED (denies excess requests) rather
    than failing OPEN (allowing all requests) when Redis is down.
    
    Thread-safe implementation using locks.
    """
    
    def __init__(self):
        self._buckets: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Clean up old entries every 60 seconds
    
    def _cleanup_old_entries(self, window: int) -> None:
        """
        Remove stale entries that fall outside the configured window.

        Args:
            window: Window size in seconds used for pruning.
        """
        now = time.time()
        
        # Only cleanup periodically to avoid performance impact
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        self._last_cleanup = now
        cutoff = now - window - 60  # Add 60s buffer
        
        keys_to_delete = []
        for key, timestamps in self._buckets.items():
            # Filter old timestamps
            self._buckets[key] = [ts for ts in timestamps if ts > cutoff]
            if not self._buckets[key]:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del self._buckets[key]
    
    def check(self, key: str, limit: int, window: int) -> Tuple[bool, int, int]:
        """
        Check if request is allowed under rate limit.
        
        Args:
            key: Identifier (e.g., "auth:192.168.1.1")
            limit: Maximum requests allowed
            window: Time window in seconds
            
        Returns:
            Tuple of (allowed, remaining, reset_at_timestamp)
        """
        now = time.time()
        
        with self._lock:
            self._cleanup_old_entries(window)
            
            # Get or create bucket
            if key not in self._buckets:
                self._buckets[key] = []
            
            # Remove old timestamps outside window
            window_start = now - window
            self._buckets[key] = [ts for ts in self._buckets[key] if ts > window_start]
            
            current_count = len(self._buckets[key])
            remaining = max(0, limit - current_count)
            
            # Calculate reset time (when oldest entry expires)
            if self._buckets[key]:
                reset_at = int(self._buckets[key][0] + window)
            else:
                reset_at = int(now + window)
            
            if current_count < limit:
                # Allow and record
                self._buckets[key].append(now)
                return True, remaining - 1, reset_at
            else:
                # Deny
                return False, 0, reset_at
    
    def record_failure(self, key: str) -> None:
        """
        Record a failed attempt for a given key.

        Args:
            key: Identifier bucket to increment.
        """
        now = time.time()
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = []
            self._buckets[key].append(now)
    
    def reset(self, key: str) -> None:
        """
        Clear all tracked requests for a given key.

        Args:
            key: Identifier bucket to clear.
        """
        with self._lock:
            if key in self._buckets:
                del self._buckets[key]


# Global in-memory fallback instance
_memory_limiter = InMemoryRateLimiter()


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining: int
    limit: int
    reset_at: int  # Unix timestamp
    retry_after: Optional[int] = None  # Seconds until retry allowed
    
    def to_headers(self) -> dict:
        """
        Convert rate limit metadata into HTTP response headers.

        Returns:
            Dictionary of rate limit header names to values.
        """
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_at),
        }
        if self.retry_after:
            headers["Retry-After"] = str(self.retry_after)
        return headers


@dataclass
class LockoutResult:
    """Result of an account lockout check."""
    is_locked: bool
    failure_count: int
    lockout_until: Optional[int] = None  # Unix timestamp when lockout expires
    retry_after: Optional[int] = None  # Seconds until lockout expires


# =============================================================================
# Account Lockout Configuration
# =============================================================================

class AccountLockout:
    """
    Account lockout mechanism to prevent brute force attacks.
    
    Features:
    - Progressive lockout: longer lockouts after more failures
    - Configurable thresholds and durations
    - Automatic expiry
    - Reset on successful authentication
    
    Lockout progression:
    - 3 failures: 1 minute lockout
    - 5 failures: 5 minute lockout
    - 7 failures: 15 minute lockout
    - 10+ failures: 1 hour lockout
    
    Usage:
        lockout = get_account_lockout()
        
        # Check before auth attempt
        result = lockout.check("user@example.com")
        if result.is_locked:
            raise AccountLockedError(retry_after=result.retry_after)
        
        # Record failure after failed auth
        lockout.record_failure("user@example.com")
        
        # Clear on successful auth
        lockout.clear("user@example.com")
    """
    
    # Lockout thresholds: (failure_count, lockout_seconds)
    LOCKOUT_THRESHOLDS = [
        (3, 60),      # 3 failures: 1 minute
        (5, 300),     # 5 failures: 5 minutes
        (7, 900),     # 7 failures: 15 minutes
        (10, 3600),   # 10+ failures: 1 hour
    ]
    
    # Key prefix for Redis
    KEY_PREFIX = "lockout:"
    
    # Failure tracking window (how long to remember failures)
    FAILURE_WINDOW = 3600  # 1 hour
    
    def __init__(self):
        self._memory_store: Dict[str, Dict] = {}
        self._lock = threading.Lock()
    
    def _get_lockout_duration(self, failure_count: int) -> int:
        """
        Determine lockout duration for a failure count.

        Args:
            failure_count: Number of consecutive failures.

        Returns:
            Lockout duration in seconds.
        """
        duration = 0
        for threshold, seconds in self.LOCKOUT_THRESHOLDS:
            if failure_count >= threshold:
                duration = seconds
        return duration
    
    def _get_key(self, identifier: str) -> str:
        """
        Build the cache key for lockout tracking.

        Args:
            identifier: User email or IP address.

        Returns:
            Cache key string.
        """
        return f"{self.KEY_PREFIX}{identifier}"
    
    def check(self, identifier: str) -> LockoutResult:
        """
        Check if an identifier (email/IP) is locked out.
        
        Args:
            identifier: User email or IP address
            
        Returns:
            LockoutResult with lockout status
        """
        now = int(time.time())
        
        # Try Redis first
        if cache.is_available:
            return self._check_redis(identifier, now)
        
        # Fall back to in-memory
        return self._check_memory(identifier, now)
    
    def _check_redis(self, identifier: str, now: int) -> LockoutResult:
        """
        Evaluate lockout status using Redis state.

        Args:
            identifier: User email or IP address.
            now: Current epoch seconds.

        Returns:
            LockoutResult representing current status.
        """
        key = self._get_key(identifier)
        
        try:
            data = cache.get_json(key)
            if not data:
                return LockoutResult(is_locked=False, failure_count=0)
            
            failure_count = data.get("failures", 0)
            lockout_until = data.get("lockout_until", 0)
            
            # Check if currently locked
            if lockout_until > now:
                retry_after = lockout_until - now
                return LockoutResult(
                    is_locked=True,
                    failure_count=failure_count,
                    lockout_until=lockout_until,
                    retry_after=retry_after,
                )
            
            return LockoutResult(
                is_locked=False,
                failure_count=failure_count,
            )
            
        except Exception as e:
            logger.error("lockout_check_error", error=str(e))
            return LockoutResult(is_locked=False, failure_count=0)
    
    def _check_memory(self, identifier: str, now: int) -> LockoutResult:
        """
        Evaluate lockout status using in-memory state.

        Args:
            identifier: User email or IP address.
            now: Current epoch seconds.

        Returns:
            LockoutResult representing current status.
        """
        with self._lock:
            data = self._memory_store.get(identifier, {})
            
            if not data:
                return LockoutResult(is_locked=False, failure_count=0)
            
            failure_count = data.get("failures", 0)
            lockout_until = data.get("lockout_until", 0)
            
            # Check if currently locked
            if lockout_until > now:
                retry_after = lockout_until - now
                return LockoutResult(
                    is_locked=True,
                    failure_count=failure_count,
                    lockout_until=lockout_until,
                    retry_after=retry_after,
                )
            
            return LockoutResult(
                is_locked=False,
                failure_count=failure_count,
            )
    
    def record_failure(self, identifier: str) -> LockoutResult:
        """
        Record a failed authentication attempt.
        
        Args:
            identifier: User email or IP address
            
        Returns:
            Updated lockout status
        """
        now = int(time.time())
        
        # Try Redis first
        if cache.is_available:
            return self._record_failure_redis(identifier, now)
        
        # Fall back to in-memory
        return self._record_failure_memory(identifier, now)
    
    def _record_failure_redis(self, identifier: str, now: int) -> LockoutResult:
        """
        Record a failed attempt in Redis state.

        Args:
            identifier: User email or IP address.
            now: Current epoch seconds.

        Returns:
            Updated LockoutResult after recording.
        """
        key = self._get_key(identifier)
        
        try:
            # Get current data
            data = cache.get_json(key) or {"failures": 0, "lockout_until": 0}
            
            # Increment failure count
            failure_count = data.get("failures", 0) + 1
            
            # Calculate new lockout duration
            lockout_duration = self._get_lockout_duration(failure_count)
            lockout_until = now + lockout_duration if lockout_duration > 0 else 0
            
            # Update data
            new_data = {
                "failures": failure_count,
                "lockout_until": lockout_until,
                "last_failure": now,
            }
            
            # Store with TTL
            cache.set_json(key, new_data, ttl=self.FAILURE_WINDOW)
            
            logger.warning(
                "auth_failure_recorded",
                identifier=identifier[:20] + "..." if len(identifier) > 20 else identifier,
                failure_count=failure_count,
                lockout_seconds=lockout_duration,
            )
            
            return LockoutResult(
                is_locked=lockout_duration > 0,
                failure_count=failure_count,
                lockout_until=lockout_until if lockout_duration > 0 else None,
                retry_after=lockout_duration if lockout_duration > 0 else None,
            )
            
        except Exception as e:
            logger.error("lockout_record_error", error=str(e))
            return LockoutResult(is_locked=False, failure_count=0)
    
    def _record_failure_memory(self, identifier: str, now: int) -> LockoutResult:
        """
        Record a failed attempt in the in-memory store.

        Args:
            identifier: User email or IP address.
            now: Current epoch seconds.

        Returns:
            Updated LockoutResult after recording.
        """
        with self._lock:
            data = self._memory_store.get(identifier, {"failures": 0, "lockout_until": 0})
            
            # Increment failure count
            failure_count = data.get("failures", 0) + 1
            
            # Calculate new lockout duration
            lockout_duration = self._get_lockout_duration(failure_count)
            lockout_until = now + lockout_duration if lockout_duration > 0 else 0
            
            # Update data
            self._memory_store[identifier] = {
                "failures": failure_count,
                "lockout_until": lockout_until,
                "last_failure": now,
            }
            
            logger.warning(
                "auth_failure_recorded_memory",
                identifier=identifier[:20] + "..." if len(identifier) > 20 else identifier,
                failure_count=failure_count,
                lockout_seconds=lockout_duration,
            )
            
            return LockoutResult(
                is_locked=lockout_duration > 0,
                failure_count=failure_count,
                lockout_until=lockout_until if lockout_duration > 0 else None,
                retry_after=lockout_duration if lockout_duration > 0 else None,
            )
    
    def clear(self, identifier: str) -> None:
        """
        Clear lockout status after successful authentication.
        
        Args:
            identifier: User email or IP address
        """
        # Clear from Redis
        if cache.is_available:
            try:
                cache.delete(self._get_key(identifier))
            except Exception as e:
                logger.error("lockout_clear_error", error=str(e))
        
        # Clear from memory
        with self._lock:
            self._memory_store.pop(identifier, None)
        
        logger.debug("lockout_cleared", identifier=identifier[:20])
    
    def get_status(self, identifier: str) -> LockoutResult:
        """Get current lockout status without recording a failure."""
        return self.check(identifier)


# Global singleton for account lockout
_account_lockout: Optional[AccountLockout] = None


def get_account_lockout() -> AccountLockout:
    """Get the AccountLockout singleton."""
    global _account_lockout
    if _account_lockout is None:
        _account_lockout = AccountLockout()
    return _account_lockout


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
            
        Note:
            Falls back to in-memory rate limiting if Redis is unavailable.
            This ensures the system fails CLOSED (still rate limits) rather
            than failing OPEN (allowing unlimited requests).
        """
        config = self._get_config(endpoint)
        
        # If Redis unavailable, use in-memory fallback (fail closed)
        if not self.is_available:
            key = f"{config['key_prefix']}{identifier}"
            allowed, remaining, reset_at = _memory_limiter.check(
                key, config["limit"], config["window"]
            )
            
            if not allowed:
                logger.warning(
                    "rate_limit_exceeded_fallback",
                    endpoint=endpoint,
                    identifier=identifier[:20],
                    message="Rate limited via in-memory fallback (Redis unavailable)",
                )
            
            return RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                limit=config["limit"],
                reset_at=reset_at,
                retry_after=reset_at - int(time.time()) if not allowed else None,
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
        
        config = self._get_config(strict_endpoint)
        key = self._get_key(strict_endpoint, identifier)
        
        # Use in-memory fallback if Redis unavailable
        if not self.is_available:
            _memory_limiter.record_failure(key)
            logger.info(
                "auth_failure_recorded_fallback",
                identifier=identifier[:20],
            )
            return
        
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
            # Fallback to in-memory on error
            _memory_limiter.record_failure(key)
            logger.error("record_failure_error", error=str(e))
    
    def reset(self, endpoint: str, identifier: str) -> None:
        """
        Reset rate limit for an identifier.
        
        Useful after successful authentication to clear failure counter.
        
        Args:
            endpoint: The endpoint type
            identifier: Client identifier
        """
        key = self._get_key(endpoint, identifier)
        strict_key = self._get_key(f"{endpoint}_strict", identifier)
        
        # Reset in-memory fallback too
        _memory_limiter.reset(key)
        _memory_limiter.reset(strict_key)
        
        if not self.is_available:
            logger.debug(
                "rate_limit_reset_fallback",
                endpoint=endpoint,
                identifier=identifier[:20],
            )
            return
        
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
        
        # Note: For status checks, we still report approximate status
        # even when Redis is unavailable (using in-memory state)
        if not self.is_available:
            # Check in-memory state without consuming
            key = f"{config['key_prefix']}{identifier}"
            # Use a check with cost=0 equivalent by just reading state
            with _memory_limiter._lock:
                now = time.time()
                window_start = now - config["window"]
                timestamps = _memory_limiter._buckets.get(key, [])
                current = len([ts for ts in timestamps if ts > window_start])
                remaining = max(0, config["limit"] - current)
                reset_at = int(timestamps[0] + config["window"]) if timestamps else int(now + config["window"])
            
            return RateLimitResult(
                allowed=remaining > 0,
                remaining=remaining,
                limit=config["limit"],
                reset_at=reset_at,
                retry_after=reset_at - int(now) if remaining == 0 else None,
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

