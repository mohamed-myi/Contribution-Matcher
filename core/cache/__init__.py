"""
Redis Caching Layer.

Provides Redis-based caching with connection pooling for:
- JSON data (API responses, computed scores)
- Pickle data (ML models, large objects)
- Automatic cache invalidation

Usage:
    from core.cache import cache, cached, CacheKeys

    # Direct cache access
    cache.set_json("user:123:scores", scores, ttl=300)
    scores = cache.get_json("user:123:scores")

    # Decorator-based caching
    @cached(CacheKeys.user_scores, ttl=300)
    def get_user_scores(user_id: int):
        return expensive_computation()
"""

from core.cache.cache_keys import CacheKeys
from core.cache.decorators import cached, cached_model
from core.cache.redis_client import RedisCache, cache

__all__ = [
    "RedisCache",
    "cache",
    "CacheKeys",
    "cached",
    "cached_model",
]
