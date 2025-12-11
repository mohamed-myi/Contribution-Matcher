"""
Cache Infrastructure.

Provides Redis-based caching for:
- Top matches results
- Score calculations
- API responses
"""

from core.cache import cache, CacheKeys

__all__ = ["cache", "CacheKeys"]
