"""
Stream Processor Package.

Dedicated GitHub issue streaming service for continuous discovery.

Features:
- Async GraphQL client for efficient GitHub queries
- Cursor-based pagination for no page limits
- Smart rate limiting with exponential backoff
- Redis Streams for reliable message queuing
- APScheduler for 24/7 continuous operation

Performance targets:
- 5K+ issues/hour sustained throughput
- <5% duplicate rate
- Zero GitHub API rate limit violations
- 100K+ issues discovered in 24 hours
"""

__version__ = "1.0.0"
