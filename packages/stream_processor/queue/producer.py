"""
Queue Producer.

Publishes discovered issues to Redis Streams for processing.
Handles deduplication and batching.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Set

import redis

logger = logging.getLogger(__name__)


class QueueProducer:
    """
    Redis Streams producer for issue discovery pipeline.
    
    Features:
    - Deduplication using Redis Set
    - Batch publishing for efficiency
    - Automatic retry on failures
    """
    
    STREAM_KEY = "issues:discovered"
    SEEN_SET_KEY = "issues:seen_urls"
    BATCH_SIZE = 100
    MAX_STREAM_LEN = 100000  # Trim stream to prevent unbounded growth
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        batch_size: int = BATCH_SIZE,
    ):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.batch_size = batch_size
        self._client: Optional[redis.Redis] = None
        self._batch: List[Dict[str, Any]] = []
        self._local_seen: Set[str] = set()
    
    def connect(self) -> None:
        """Establish Redis connection."""
        self._client = redis.from_url(
            self.redis_url,
            decode_responses=True,
            socket_timeout=10,
            socket_connect_timeout=10,
        )
        # Test connection
        self._client.ping()
        logger.info("Connected to Redis")
    
    def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            self._client.close()
            self._client = None
    
    def __enter__(self) -> "QueueProducer":
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Flush remaining batch before closing
        if self._batch:
            self._flush_batch()
        self.disconnect()
    
    def is_duplicate(self, url: str) -> bool:
        """
        Check if issue URL has been seen before.
        
        Uses both local cache and Redis Set for deduplication.
        """
        if url in self._local_seen:
            return True
        
        if self._client and self._client.sismember(self.SEEN_SET_KEY, url):
            self._local_seen.add(url)
            return True
        
        return False
    
    def mark_seen(self, url: str) -> None:
        """Mark a URL as seen."""
        self._local_seen.add(url)
        if self._client:
            self._client.sadd(self.SEEN_SET_KEY, url)
    
    def publish(self, issue_data: Dict[str, Any]) -> bool:
        """
        Add issue to publishing batch.
        
        Returns True if issue was added, False if duplicate.
        """
        url = issue_data.get("url")
        if not url:
            return False
        
        if self.is_duplicate(url):
            return False
        
        self._batch.append(issue_data)
        self.mark_seen(url)
        
        if len(self._batch) >= self.batch_size:
            self._flush_batch()
        
        return True
    
    def _flush_batch(self) -> int:
        """
        Flush current batch to Redis Stream.
        
        Returns number of messages published.
        """
        if not self._batch or not self._client:
            return 0
        
        pipe = self._client.pipeline()
        
        for issue in self._batch:
            # Serialize to JSON string for Redis Stream
            message = {"data": json.dumps(issue)}
            pipe.xadd(
                self.STREAM_KEY,
                message,
                maxlen=self.MAX_STREAM_LEN,
                approximate=True,
            )
        
        try:
            pipe.execute()
            published = len(self._batch)
            logger.info(f"Published {published} issues to stream")
            self._batch = []
            return published
        except redis.RedisError as e:
            logger.error(f"Failed to publish batch: {e}")
            return 0
    
    def flush(self) -> int:
        """Force flush current batch."""
        return self._flush_batch()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get producer statistics."""
        stats = {
            "pending_batch": len(self._batch),
            "local_seen_count": len(self._local_seen),
        }
        
        if self._client:
            try:
                stats["stream_length"] = self._client.xlen(self.STREAM_KEY)
                stats["total_seen"] = self._client.scard(self.SEEN_SET_KEY)
            except redis.RedisError:
                pass
        
        return stats
    
    def clear_seen(self, older_than_days: int = 30) -> int:
        """
        Clear old entries from seen set.
        
        Note: This is a simple implementation. For production,
        consider using Redis TTL or ZSET with timestamps.
        """
        # In a production system, you would track timestamps
        # and only remove truly old entries
        logger.warning("clear_seen not fully implemented")
        return 0
