"""
Caching decorators for automatic cache management.

Provides decorators that automatically check cache before execution,
cache results after computation, and handle cache failures gracefully.
"""

import functools
import hashlib
import json
from typing import Any, Callable, Optional, TypeVar, Union

from core.cache.redis_client import cache
from core.cache.cache_keys import CacheKeys
from core.logging import get_logger

logger = get_logger("cache.decorators")

T = TypeVar("T")


def _generate_cache_key(
    key_template: str,
    args: tuple,
    kwargs: dict,
) -> str:
    """
    Generate a cache key from template and function arguments.
    
    Supports:
    - Positional placeholders: {0}, {1}, etc.
    - Named placeholders: {user_id}, {limit}, etc.
    - Special __hash__ placeholder for complex args
    
    Examples:
        key_template="user:{0}:scores" with args=(123,) -> "user:123:scores"
        key_template="user:{user_id}:matches:{limit}" -> "user:123:matches:10"
    """
    try:
        # Try simple format first
        return key_template.format(*args, **kwargs)
    except (IndexError, KeyError):
        # Fall back to hash-based key for complex arguments
        args_hash = hashlib.md5(
            json.dumps({"args": str(args), "kwargs": str(kwargs)}, sort_keys=True).encode()
        ).hexdigest()[:8]
        return f"{key_template}:{args_hash}"


def cached(
    key_template: Union[str, Callable[..., str]],
    ttl: int = CacheKeys.TTL_MEDIUM,
    skip_cache_if: Optional[Callable[..., bool]] = None,
) -> Callable:
    """
    Decorator for caching function results as JSON.
    
    Args:
        key_template: Cache key template string or callable that returns key
            - String: Supports {0}, {1}, {arg_name} placeholders
            - Callable: Function that takes same args and returns key string
        ttl: Time-to-live in seconds (default: 30 minutes)
        skip_cache_if: Optional callable to skip caching conditionally
    
    Usage:
        @cached("user:{0}:scores", ttl=300)
        def get_user_scores(user_id: int):
            return expensive_computation()
        
        @cached(lambda user_id, limit: f"user:{user_id}:top:{limit}")
        def get_top_matches(user_id: int, limit: int = 10):
            return compute_matches()
    
    Notes:
        - Returns None-safe: if function returns None, it won't be cached
        - Cache failures are silent: function always executes on cache error
        - Result must be JSON-serializable
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Check if caching should be skipped
            if skip_cache_if and skip_cache_if(*args, **kwargs):
                return func(*args, **kwargs)
            
            # Generate cache key
            if callable(key_template):
                cache_key = key_template(*args, **kwargs)
            else:
                cache_key = _generate_cache_key(key_template, args, kwargs)
            
            # Try to get from cache
            cached_result = cache.get_json(cache_key)
            if cached_result is not None:
                logger.debug("cache_hit", key=cache_key)
                return cached_result
            
            # Compute result
            logger.debug("cache_miss", key=cache_key)
            result = func(*args, **kwargs)
            
            # Cache the result (if not None)
            if result is not None:
                cache.set_json(cache_key, result, ttl)
            
            return result
        
        # Add cache management methods to the wrapper
        wrapper.cache_key_template = key_template
        wrapper.cache_ttl = ttl
        
        def invalidate(*args, **kwargs) -> bool:
            """Invalidate cache for specific arguments."""
            if callable(key_template):
                cache_key = key_template(*args, **kwargs)
            else:
                cache_key = _generate_cache_key(key_template, args, kwargs)
            return cache.delete(cache_key)
        
        wrapper.invalidate = invalidate
        
        return wrapper
    
    return decorator


def cached_model(
    key: str,
    ttl: int = CacheKeys.TTL_DAY,
    loader: Optional[Callable[[], T]] = None,
) -> Callable:
    """
    Decorator for caching ML models and large objects.
    
    Uses pickle serialization instead of JSON for complex objects.
    Implements lazy loading with 3-tier hierarchy:
    1. In-memory (instance variable)
    2. Redis cache
    3. Disk/computation (loader function)
    
    Args:
        key: Cache key for the model
        ttl: Time-to-live in seconds (default: 24 hours)
        loader: Optional loader function if not the decorated function
    
    Usage:
        @cached_model("ml:model:scorer", ttl=86400)
        def load_scorer_model():
            return joblib.load("models/scorer.pkl")
        
        # First call: loads from disk, caches in Redis
        model = load_scorer_model()
        
        # Subsequent calls: returns from Redis (fast)
        model = load_scorer_model()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # In-memory cache for this specific model
        _memory_cache: dict = {"model": None}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Tier 1: Check in-memory cache
            if _memory_cache["model"] is not None:
                logger.debug("model_cache_hit", tier="memory", key=key)
                return _memory_cache["model"]
            
            # Tier 2: Check Redis cache
            cached_model = cache.get_model(key)
            if cached_model is not None:
                logger.debug("model_cache_hit", tier="redis", key=key)
                _memory_cache["model"] = cached_model
                return cached_model
            
            # Tier 3: Load from disk/compute
            logger.info("model_cache_miss", key=key)
            load_fn = loader if loader else func
            model = load_fn(*args, **kwargs)
            
            # Cache in Redis
            if model is not None:
                cache.set_model(key, model, ttl)
                _memory_cache["model"] = model
            
            return model
        
        def invalidate() -> bool:
            """Invalidate both memory and Redis cache."""
            _memory_cache["model"] = None
            return cache.delete(key)
        
        def refresh(*args, **kwargs) -> T:
            """Force reload from disk/computation."""
            invalidate()
            return wrapper(*args, **kwargs)
        
        wrapper.invalidate = invalidate
        wrapper.refresh = refresh
        wrapper.cache_key = key
        
        return wrapper
    
    return decorator


class CachedProperty:
    """
    Descriptor for caching property values in Redis.
    
    Similar to @property but caches the result in Redis.
    
    Usage:
        class ScoringService:
            @CachedProperty("ml:model:scorer", ttl=86400)
            def ml_model(self):
                return joblib.load("models/scorer.pkl")
    """
    
    def __init__(
        self,
        key: str,
        ttl: int = CacheKeys.TTL_DAY,
        use_pickle: bool = True,
    ):
        self.key = key
        self.ttl = ttl
        self.use_pickle = use_pickle
        self.func = None
        self.attr_name = None
    
    def __set_name__(self, owner, name):
        self.attr_name = f"_cached_{name}"
    
    def __call__(self, func: Callable) -> "CachedProperty":
        self.func = func
        return self
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        
        # Check instance cache first
        cached_value = getattr(obj, self.attr_name, None)
        if cached_value is not None:
            return cached_value
        
        # Check Redis cache
        if self.use_pickle:
            cached_value = cache.get_model(self.key)
        else:
            cached_value = cache.get_json(self.key)
        
        if cached_value is not None:
            setattr(obj, self.attr_name, cached_value)
            return cached_value
        
        # Compute and cache
        value = self.func(obj)
        if value is not None:
            if self.use_pickle:
                cache.set_model(self.key, value, self.ttl)
            else:
                cache.set_json(self.key, value, self.ttl)
            setattr(obj, self.attr_name, value)
        
        return value

