"""
Queue Module.

Provides Redis Streams-based message queuing for:
- Issue data publishing
- Deduplication with seen IDs
- Batch writes for efficiency
"""

from .producer import QueueProducer

__all__ = ["QueueProducer"]
