"""
Redis client with connection pooling.

Provides a singleton Redis client with:
- Connection pooling (max 50 connections)
- JSON serialization for API responses
- Pickle serialization for ML models
- Graceful degradation when Redis is unavailable
"""

import json
import pickle
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional, TypeVar

if TYPE_CHECKING:
    import redis
    from redis.exceptions import ConnectionError, TimeoutError

    REDIS_AVAILABLE = True
else:
    try:
        import redis
        from redis.exceptions import ConnectionError, TimeoutError

        REDIS_AVAILABLE = True
    except ImportError:
        REDIS_AVAILABLE = False
        redis = None  # type: ignore[assignment]

from core.config import get_settings
from core.logging import get_logger

logger = get_logger("cache")

T = TypeVar("T")


class RedisCache:
    """
    Redis cache client with connection pooling.

    Features:
    - Singleton pattern for connection reuse
    - Connection pooling (configurable max connections)
    - JSON and Pickle serialization
    - Graceful fallback when Redis is unavailable

    Usage:
        from core.cache import cache

        # JSON data
        cache.set_json("key", {"data": "value"}, ttl=300)
        data = cache.get_json("key")

        # Binary/Model data
        cache.set_model("ml:model", trained_model, ttl=86400)
        model = cache.get_model("ml:model")
    """

    _instance: Optional["RedisCache"] = None
    _pool: Optional["redis.ConnectionPool"] = None
    _initialized: bool = False
    _available: bool = False

    def __new__(cls) -> "RedisCache":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent re-initialization
        pass

    def initialize(self, force: bool = False) -> bool:
        """
        Initialize Redis connection pool.

        Args:
            force: Force re-initialization even if already initialized

        Returns:
            True if Redis is available and connected, False otherwise
        """
        if self._initialized and not force:
            return self._available

        if not REDIS_AVAILABLE:
            logger.warning("Redis package not installed. Caching disabled.")
            self._available = False
            self._initialized = True
            return False

        try:
            settings = get_settings()

            # Create connection pool
            self._pool = redis.ConnectionPool(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                max_connections=50,
                socket_timeout=5,
                socket_connect_timeout=5,
                decode_responses=False,  # We handle encoding ourselves
            )

            # Test connection
            client = redis.Redis(connection_pool=self._pool)
            client.ping()

            self._available = True
            self._initialized = True
            logger.info("redis_connected", host=settings.redis_host, port=settings.redis_port)
            return True

        except (ConnectionError, TimeoutError) as e:
            logger.warning("redis_connection_failed", error=str(e))
            self._available = False
            self._initialized = True
            return False
        except Exception as e:
            logger.warning("redis_init_error", error=str(e))
            self._available = False
            self._initialized = True
            return False

    @property
    def client(self) -> Optional["redis.Redis"]:
        """Get Redis client from pool."""
        if not self._initialized:
            self.initialize()

        if not self._available or self._pool is None:
            return None

        return redis.Redis(connection_pool=self._pool)

    @property
    def is_available(self) -> bool:
        """Check if Redis is available."""
        if not self._initialized:
            self.initialize()
        return self._available

    # =========================================================================
    # JSON Operations (for API responses, scores, etc.)
    # =========================================================================

    def get_json(self, key: str) -> dict | None:
        """
        Get JSON data from cache.

        Args:
            key: Cache key

        Returns:
            Parsed JSON data or None if not found/unavailable
        """
        if not self.is_available:
            return None

        client = self.client
        if client is None:
            return None

        try:
            data = client.get(key)
            if data is None:
                return None
            if isinstance(data, bytes):
                parsed = json.loads(data.decode("utf-8"))
                return parsed if isinstance(parsed, dict) else None
            # Handle case where data might be a string or other type
            if isinstance(data, str):
                parsed = json.loads(data)
                return parsed if isinstance(parsed, dict) else None
            return None
        except (json.JSONDecodeError, ConnectionError, TimeoutError) as e:
            logger.debug("cache_get_error", key=key, error=str(e))
            return None

    def set_json(
        self,
        key: str,
        value: dict | list,
        ttl: int = 3600,
    ) -> bool:
        """
        Store JSON data in cache.

        Args:
            key: Cache key
            value: Data to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (default: 1 hour)

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.is_available:
            return False

        client = self.client
        if client is None:
            return False

        try:
            serialized = json.dumps(value).encode("utf-8")
            client.setex(key, ttl, serialized)
            return True
        except (TypeError, ConnectionError, TimeoutError) as e:
            logger.debug("cache_set_error", key=key, error=str(e))
            return False

    def get_json_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], dict[Any, Any]],
        ttl: int = 3600,
    ) -> dict[Any, Any] | None:
        """
        Get from cache or compute and cache the result.

        Args:
            key: Cache key
            compute_fn: Function to call if cache miss
            ttl: Time-to-live in seconds

        Returns:
            Cached or computed data
        """
        result = self.get_json(key)
        if result is not None:
            return result

        result = compute_fn()
        if result is not None:
            self.set_json(key, result, ttl)
        return result

    # =========================================================================
    # Model Operations (for ML models, embeddings, etc.)
    # =========================================================================

    def get_model(self, key: str) -> Any | None:
        """
        Get pickled model from cache.

        Args:
            key: Cache key

        Returns:
            Unpickled object or None if not found/unavailable
        """
        if not self.is_available:
            return None

        client = self.client
        if client is None:
            return None

        try:
            data = client.get(key)
            if data is None:
                return None
            if isinstance(data, bytes):
                return pickle.loads(data)
            # Handle case where data might already be unpickled
            return data
        except (pickle.UnpicklingError, ConnectionError, TimeoutError) as e:
            logger.debug("cache_get_model_error", key=key, error=str(e))
            return None

    def set_model(
        self,
        key: str,
        value: Any,
        ttl: int = 86400,  # 24 hours default for models
    ) -> bool:
        """
        Store pickled model in cache.

        Args:
            key: Cache key
            value: Object to cache (must be picklable)
            ttl: Time-to-live in seconds (default: 24 hours)

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.is_available:
            return False

        client = self.client
        if client is None:
            return False

        try:
            serialized = pickle.dumps(value)
            client.setex(key, ttl, serialized)
            return True
        except (pickle.PicklingError, ConnectionError, TimeoutError) as e:
            logger.debug("cache_set_model_error", key=key, error=str(e))
            return False

    # =========================================================================
    # Key Operations
    # =========================================================================

    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        if not self.is_available:
            return False

        client = self.client
        if client is None:
            return False

        try:
            client.delete(key)
            return True
        except (ConnectionError, TimeoutError):
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Redis pattern (e.g., "user:123:*")

        Returns:
            Number of keys deleted
        """
        if not self.is_available:
            return 0

        client = self.client
        if client is None:
            return 0

        try:
            keys = client.keys(pattern)
            if keys and isinstance(keys, (list, tuple)):
                deleted = client.delete(*keys)
                if deleted is not None:
                    # Handle both int and awaitable results
                    if isinstance(deleted, (int, float)):
                        return int(deleted)
                    # If it's an awaitable or other type, return 0
                    return 0
                return 0
            return 0
        except (ConnectionError, TimeoutError):
            return 0

    def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        if not self.is_available:
            return False

        client = self.client
        if client is None:
            return False

        try:
            result = client.exists(key)
            return bool(result) if result is not None else False
        except (ConnectionError, TimeoutError):
            return False

    def ttl(self, key: str) -> int:
        """Get remaining TTL for a key in seconds."""
        if not self.is_available:
            return -1

        client = self.client
        if client is None:
            return -1

        try:
            result = client.ttl(key)
            if result is None:
                return -1
            if isinstance(result, (int, float)):
                return int(result)
            # Handle case where result might be an awaitable or other type
            return -1
        except (ConnectionError, TimeoutError):
            return -1

    def flush_all(self) -> bool:
        """
        Clear all keys in the current database.

        USE WITH CAUTION - this clears all cached data.
        """
        if not self.is_available:
            return False

        client = self.client
        if client is None:
            return False

        try:
            client.flushdb()
            return True
        except (ConnectionError, TimeoutError):
            return False

    # =========================================================================
    # Health Check
    # =========================================================================

    def health_check(self) -> dict[str, Any]:
        """
        Get cache health status.

        Returns:
            Dictionary with health information
        """
        status: dict[str, Any] = {
            "available": self._available,
            "initialized": self._initialized,
        }

        if self.is_available:
            client = self.client
            if client is None:
                status["status"] = "unavailable"
                return status

            try:
                memory_info = client.info("memory")
                clients_info = client.info("clients")

                # Handle both dict and string responses
                if isinstance(memory_info, dict):
                    status["memory_used"] = memory_info.get("used_memory_human", "unknown")
                else:
                    status["memory_used"] = "unknown"

                if isinstance(clients_info, dict):
                    status["connected_clients"] = clients_info.get("connected_clients", 0)
                else:
                    status["connected_clients"] = 0

                status["status"] = "healthy"
            except (ConnectionError, TimeoutError):
                status["status"] = "degraded"
        else:
            status["status"] = "unavailable"

        return status


# Global singleton instance
cache = RedisCache()
