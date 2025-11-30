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
from typing import Any, Dict, List, Optional, TypeVar, Union

try:
    import redis
    from redis.exceptions import ConnectionError, TimeoutError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

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
            logger.info(f"Redis connected: {settings.redis_host}:{settings.redis_port}")
            return True
            
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            self._available = False
            self._initialized = True
            return False
        except Exception as e:
            logger.warning(f"Redis initialization error: {e}. Caching disabled.")
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
    
    def get_json(self, key: str) -> Optional[Dict]:
        """
        Get JSON data from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Parsed JSON data or None if not found/unavailable
        """
        if not self.is_available:
            return None
        
        try:
            data = self.client.get(key)
            if data is None:
                return None
            return json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, ConnectionError, TimeoutError) as e:
            logger.debug(f"Cache get error for {key}: {e}")
            return None
    
    def set_json(
        self,
        key: str,
        value: Union[Dict, List],
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
        
        try:
            serialized = json.dumps(value).encode("utf-8")
            self.client.setex(key, ttl, serialized)
            return True
        except (TypeError, ConnectionError, TimeoutError) as e:
            logger.debug(f"Cache set error for {key}: {e}")
            return False
    
    def get_json_or_compute(
        self,
        key: str,
        compute_fn: callable,
        ttl: int = 3600,
    ) -> Optional[Dict]:
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
    
    def get_model(self, key: str) -> Optional[Any]:
        """
        Get pickled model from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Unpickled object or None if not found/unavailable
        """
        if not self.is_available:
            return None
        
        try:
            data = self.client.get(key)
            if data is None:
                return None
            return pickle.loads(data)
        except (pickle.UnpicklingError, ConnectionError, TimeoutError) as e:
            logger.debug(f"Cache get_model error for {key}: {e}")
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
        
        try:
            serialized = pickle.dumps(value)
            self.client.setex(key, ttl, serialized)
            return True
        except (pickle.PicklingError, ConnectionError, TimeoutError) as e:
            logger.debug(f"Cache set_model error for {key}: {e}")
            return False
    
    # =========================================================================
    # Key Operations
    # =========================================================================
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        if not self.is_available:
            return False
        
        try:
            self.client.delete(key)
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
        
        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except (ConnectionError, TimeoutError):
            return 0
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        if not self.is_available:
            return False
        
        try:
            return bool(self.client.exists(key))
        except (ConnectionError, TimeoutError):
            return False
    
    def ttl(self, key: str) -> int:
        """Get remaining TTL for a key in seconds."""
        if not self.is_available:
            return -1
        
        try:
            return self.client.ttl(key)
        except (ConnectionError, TimeoutError):
            return -1
    
    def flush_all(self) -> bool:
        """
        Clear all keys in the current database.
        
        USE WITH CAUTION - this clears all cached data.
        """
        if not self.is_available:
            return False
        
        try:
            self.client.flushdb()
            return True
        except (ConnectionError, TimeoutError):
            return False
    
    # =========================================================================
    # Health Check
    # =========================================================================
    
    def health_check(self) -> Dict[str, Any]:
        """
        Get cache health status.
        
        Returns:
            Dictionary with health information
        """
        status = {
            "available": self._available,
            "initialized": self._initialized,
        }
        
        if self.is_available:
            try:
                info = self.client.info("memory")
                status["memory_used"] = info.get("used_memory_human", "unknown")
                status["connected_clients"] = self.client.info("clients").get(
                    "connected_clients", 0
                )
                status["status"] = "healthy"
            except (ConnectionError, TimeoutError):
                status["status"] = "degraded"
        else:
            status["status"] = "unavailable"
        
        return status


# Global singleton instance
cache = RedisCache()

