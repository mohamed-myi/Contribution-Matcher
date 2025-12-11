"""
Tests for Stream Processor Package.

Tests:
- GitHub GraphQL client
- Rate limiting
- Queue producer
- Scheduler
"""

from unittest.mock import patch

import pytest

# Check if aiohttp is available
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


@pytest.mark.skipif(not HAS_AIOHTTP, reason="aiohttp not installed")
class TestRateLimiter:
    """Tests for RateLimiter class."""
    
    def test_initial_state(self):
        """Test rate limiter initial state."""
        from packages.stream_processor.github.client import RateLimiter
        
        limiter = RateLimiter(requests_per_hour=5000)
        
        assert limiter.remaining == 5000
        assert limiter.backoff_factor == 1.0
    
    def test_update_from_response(self):
        """Test updating rate limit from API response."""
        from packages.stream_processor.github.client import RateLimiter
        
        limiter = RateLimiter()
        
        limiter.update_from_response({
            "remaining": 4500,
            "resetAt": "2024-12-10T12:00:00Z",
        })
        
        assert limiter.remaining == 4500
        assert limiter.reset_at is not None
    
    def test_backoff_increase(self):
        """Test exponential backoff increases correctly."""
        from packages.stream_processor.github.client import RateLimiter
        
        limiter = RateLimiter()
        
        initial_backoff = limiter.backoff_factor
        limiter.increase_backoff()
        
        assert limiter.backoff_factor == initial_backoff * 2
    
    def test_backoff_reset(self):
        """Test backoff reset reduces factor."""
        from packages.stream_processor.github.client import RateLimiter
        
        limiter = RateLimiter()
        limiter.backoff_factor = 8.0
        
        limiter.reset_backoff()
        
        assert limiter.backoff_factor == 4.0


class TestQueueProducer:
    """Tests for QueueProducer class."""
    
    def test_is_duplicate_local(self):
        """Test local duplicate detection."""
        from packages.stream_processor.queue.producer import QueueProducer
        
        producer = QueueProducer()
        producer._local_seen.add("http://example.com/issue/1")
        
        assert producer.is_duplicate("http://example.com/issue/1") is True
        assert producer.is_duplicate("http://example.com/issue/2") is False
    
    def test_mark_seen(self):
        """Test marking URL as seen."""
        from packages.stream_processor.queue.producer import QueueProducer
        
        producer = QueueProducer()
        
        producer.mark_seen("http://example.com/issue/1")
        
        assert "http://example.com/issue/1" in producer._local_seen
    
    def test_publish_filters_duplicates(self):
        """Test publish returns False for duplicates."""
        from packages.stream_processor.queue.producer import QueueProducer
        
        producer = QueueProducer()
        
        issue = {"url": "http://example.com/issue/1", "title": "Test"}
        
        assert producer.publish(issue) is True
        assert producer.publish(issue) is False  # Duplicate
    
    def test_publish_missing_url(self):
        """Test publish returns False for missing URL."""
        from packages.stream_processor.queue.producer import QueueProducer
        
        producer = QueueProducer()
        
        issue = {"title": "Test"}
        
        assert producer.publish(issue) is False
    
    def test_get_stats(self):
        """Test getting producer statistics."""
        from packages.stream_processor.queue.producer import QueueProducer
        
        producer = QueueProducer()
        producer._batch = [{"url": "test"}]
        producer._local_seen = {"a", "b"}
        
        stats = producer.get_stats()
        
        assert stats["pending_batch"] == 1
        assert stats["local_seen_count"] == 2


class TestDiscoveryScheduler:
    """Tests for DiscoveryScheduler class."""
    
    def test_initial_state(self):
        """Test scheduler initial state."""
        from packages.stream_processor.scheduler import DiscoveryScheduler
        
        scheduler = DiscoveryScheduler()
        
        assert scheduler._running is False
        assert scheduler.stats == {}
    
    def test_add_discovery_jobs(self):
        """Test adding discovery jobs."""
        from packages.stream_processor.scheduler import DiscoveryScheduler
        
        scheduler = DiscoveryScheduler()
        scheduler.add_discovery_jobs()
        
        # Should have stats for each strategy
        assert len(scheduler.stats) > 0
        
        # Each strategy should have proper stats structure
        for name, stats in scheduler.stats.items():
            assert "last_run" in stats
            assert "issues_discovered" in stats
            assert "runs" in stats
            assert "errors" in stats
    
    def test_get_stats(self):
        """Test getting scheduler stats."""
        from packages.stream_processor.scheduler import DiscoveryScheduler
        
        scheduler = DiscoveryScheduler()
        scheduler.add_discovery_jobs()
        
        stats = scheduler.get_stats()
        
        assert "running" in stats
        assert "strategies" in stats
        assert "jobs" in stats


class TestGitHubGraphQLQueries:
    """Tests for GraphQL query definitions (no aiohttp needed)."""
    
    def test_search_issues_query_structure(self):
        """Test SEARCH_ISSUES_QUERY has required fields."""
        from packages.stream_processor.github.queries import SEARCH_ISSUES_QUERY
        
        assert "rateLimit" in SEARCH_ISSUES_QUERY
        assert "search" in SEARCH_ISSUES_QUERY
        assert "pageInfo" in SEARCH_ISSUES_QUERY
        assert "hasNextPage" in SEARCH_ISSUES_QUERY
        assert "endCursor" in SEARCH_ISSUES_QUERY
    
    def test_issue_details_query_structure(self):
        """Test GET_ISSUE_DETAILS_QUERY has required fields."""
        from packages.stream_processor.github.queries import GET_ISSUE_DETAILS_QUERY
        
        assert "repository" in GET_ISSUE_DETAILS_QUERY
        assert "issue" in GET_ISSUE_DETAILS_QUERY
        assert "rateLimit" in GET_ISSUE_DETAILS_QUERY


@pytest.mark.skipif(not HAS_AIOHTTP, reason="aiohttp not installed")
class TestGitHubStreamClient:
    """Tests for GitHubStreamClient."""
    
    def test_parse_issue(self):
        """Test issue parsing from GraphQL response."""
        from packages.stream_processor.github.client import GitHubStreamClient
        
        # Create client with mock token
        with patch.dict("os.environ", {"GITHUB_TOKEN": "test_token"}):
            client = GitHubStreamClient()
        
        node = {
            "id": "I_123",
            "number": 42,
            "title": "Test Issue",
            "body": "Test body",
            "url": "https://github.com/owner/repo/issues/42",
            "state": "OPEN",
            "createdAt": "2024-01-01T00:00:00Z",
            "labels": {"nodes": [{"name": "good first issue"}]},
            "repository": {
                "owner": {"login": "owner"},
                "name": "repo",
                "url": "https://github.com/owner/repo",
                "stargazerCount": 1000,
                "forkCount": 100,
                "primaryLanguage": {"name": "Python"},
                "repositoryTopics": {"nodes": []},
            },
        }
        
        parsed = client._parse_issue(node)
        
        assert parsed["github_id"] == "I_123"
        assert parsed["number"] == 42
        assert parsed["title"] == "Test Issue"
        assert parsed["repo_owner"] == "owner"
        assert parsed["repo_name"] == "repo"
        assert parsed["repo_stars"] == 1000
        assert "good first issue" in parsed["labels"]
