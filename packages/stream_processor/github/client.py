"""
Async GitHub GraphQL Client.

Features:
- Async HTTP with aiohttp
- Cursor-based pagination
- Smart rate limiting with backoff
- Connection pooling
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp

from .queries import (
    SEARCH_ISSUES_QUERY,
    GET_ISSUE_DETAILS_QUERY,
    CHECK_ISSUE_STATUS_QUERY,
    GET_REPO_METADATA_QUERY,
)

logger = logging.getLogger(__name__)

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


class RateLimiter:
    """
    Smart rate limiter with exponential backoff.
    
    Tracks GitHub API rate limits and implements
    intelligent waiting strategies.
    """
    
    def __init__(self, requests_per_hour: int = 5000):
        self.requests_per_hour = requests_per_hour
        self.remaining = requests_per_hour
        self.reset_at: Optional[datetime] = None
        self.last_request_time: float = 0
        self.min_interval = 3600 / requests_per_hour  # seconds between requests
        self.backoff_factor = 1.0
    
    def update_from_response(self, rate_limit: Dict[str, Any]) -> None:
        """Update rate limit info from GraphQL response."""
        self.remaining = rate_limit.get("remaining", self.remaining)
        reset_at_str = rate_limit.get("resetAt")
        if reset_at_str:
            self.reset_at = datetime.fromisoformat(reset_at_str.replace("Z", "+00:00"))
    
    async def wait_if_needed(self) -> None:
        """Wait if approaching rate limit or need backoff."""
        now = time.time()
        
        # Minimum interval between requests
        elapsed = now - self.last_request_time
        if elapsed < self.min_interval * self.backoff_factor:
            wait_time = (self.min_interval * self.backoff_factor) - elapsed
            await asyncio.sleep(wait_time)
        
        # If low on remaining requests, wait for reset
        if self.remaining < 100 and self.reset_at:
            now_utc = datetime.now(timezone.utc)
            if self.reset_at > now_utc:
                wait_seconds = (self.reset_at - now_utc).total_seconds()
                logger.warning(f"Rate limit low ({self.remaining}), waiting {wait_seconds:.0f}s")
                await asyncio.sleep(min(wait_seconds + 1, 300))  # Max 5 min wait
        
        self.last_request_time = time.time()
    
    def increase_backoff(self) -> None:
        """Increase backoff factor on errors."""
        self.backoff_factor = min(self.backoff_factor * 2, 32)
    
    def reset_backoff(self) -> None:
        """Reset backoff on successful requests."""
        self.backoff_factor = max(self.backoff_factor / 2, 1.0)


class GitHubStreamClient:
    """
    Async GitHub GraphQL client for streaming issue discovery.
    
    Example:
        async with GitHubStreamClient(token) as client:
            async for issue in client.search_issues("label:good-first-issue"):
                print(issue["title"])
    """
    
    def __init__(
        self,
        token: Optional[str] = None,
        max_concurrent: int = 5,
        timeout: int = 30,
    ):
        self.token = token or os.getenv("PAT_TOKEN") or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GitHub token required")
        
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.rate_limiter = RateLimiter()
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def __aenter__(self) -> "GitHubStreamClient":
        """Create aiohttp session on context entry."""
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent * 2,
            limit_per_host=self.max_concurrent,
        )
        self._session = aiohttp.ClientSession(
            connector=connector,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=aiohttp.ClientTimeout(total=self.timeout),
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close session on context exit."""
        if self._session:
            await self._session.close()
    
    async def _execute_query(
        self,
        query: str,
        variables: Dict[str, Any],
        retries: int = 3,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query with retries."""
        if not self._session:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        
        await self.rate_limiter.wait_if_needed()
        
        async with self._semaphore:
            for attempt in range(retries):
                try:
                    async with self._session.post(
                        GITHUB_GRAPHQL_URL,
                        json={"query": query, "variables": variables},
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # Update rate limit from response
                            if "data" in data and "rateLimit" in data["data"]:
                                self.rate_limiter.update_from_response(data["data"]["rateLimit"])
                            
                            # Check for GraphQL errors
                            if "errors" in data:
                                logger.warning(f"GraphQL errors: {data['errors']}")
                            
                            self.rate_limiter.reset_backoff()
                            return data.get("data", {})
                        
                        elif response.status == 403:
                            # Rate limited
                            logger.warning("Rate limited, backing off")
                            self.rate_limiter.increase_backoff()
                            await asyncio.sleep(60 * (attempt + 1))
                        
                        elif response.status >= 500:
                            # Server error, retry
                            await asyncio.sleep(5 * (attempt + 1))
                        
                        else:
                            text = await response.text()
                            logger.error(f"GitHub API error {response.status}: {text}")
                            return {}
                
                except asyncio.TimeoutError:
                    logger.warning(f"Request timeout, attempt {attempt + 1}/{retries}")
                    await asyncio.sleep(5 * (attempt + 1))
                
                except aiohttp.ClientError as e:
                    logger.error(f"Client error: {e}")
                    await asyncio.sleep(5 * (attempt + 1))
        
        return {}
    
    async def search_issues(
        self,
        query: str,
        max_results: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Search issues with cursor-based pagination.
        
        Args:
            query: GitHub search query (e.g., "label:good-first-issue is:open")
            max_results: Optional limit on results
        
        Yields:
            Issue dictionaries
        """
        cursor = None
        result_count = 0
        page_size = min(100, max_results) if max_results else 100
        
        while True:
            data = await self._execute_query(
                SEARCH_ISSUES_QUERY,
                {"query": query, "first": page_size, "after": cursor},
            )
            
            search = data.get("search", {})
            edges = search.get("edges", [])
            
            if not edges:
                break
            
            for edge in edges:
                node = edge.get("node", {})
                if node:
                    yield self._parse_issue(node)
                    result_count += 1
                    
                    if max_results and result_count >= max_results:
                        return
            
            page_info = search.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            
            cursor = page_info.get("endCursor")
    
    def _parse_issue(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Parse GraphQL issue node to standardized format."""
        repo = node.get("repository", {})
        labels = node.get("labels", {}).get("nodes", [])
        topics = repo.get("repositoryTopics", {}).get("nodes", [])
        
        return {
            "github_id": node.get("id"),
            "number": node.get("number"),
            "title": node.get("title"),
            "body": node.get("body"),
            "url": node.get("url"),
            "state": node.get("state", "").lower(),
            "created_at": node.get("createdAt"),
            "updated_at": node.get("updatedAt"),
            "closed_at": node.get("closedAt"),
            "labels": [l.get("name") for l in labels if l.get("name")],
            "repo_owner": repo.get("owner", {}).get("login"),
            "repo_name": repo.get("name"),
            "repo_url": repo.get("url"),
            "repo_stars": repo.get("stargazerCount", 0),
            "repo_forks": repo.get("forkCount", 0),
            "repo_language": repo.get("primaryLanguage", {}).get("name"),
            "repo_topics": [t.get("topic", {}).get("name") for t in topics],
            "last_commit_date": repo.get("pushedAt"),
        }
    
    async def check_issue_status(
        self,
        owner: str,
        repo: str,
        number: int,
    ) -> Dict[str, Any]:
        """Check if an issue is still open."""
        data = await self._execute_query(
            CHECK_ISSUE_STATUS_QUERY,
            {"owner": owner, "repo": repo, "number": number},
        )
        
        issue = data.get("repository", {}).get("issue", {})
        return {
            "state": issue.get("state", "").lower(),
            "state_reason": issue.get("stateReason"),
            "closed_at": issue.get("closedAt"),
        }
    
    async def get_repo_metadata(
        self,
        owner: str,
        name: str,
    ) -> Dict[str, Any]:
        """Get repository metadata."""
        data = await self._execute_query(
            GET_REPO_METADATA_QUERY,
            {"owner": owner, "name": name},
        )
        
        repo = data.get("repository", {})
        if not repo:
            return {}
        
        languages = repo.get("languages", {}).get("edges", [])
        topics = repo.get("repositoryTopics", {}).get("nodes", [])
        
        return {
            "name_with_owner": repo.get("nameWithOwner"),
            "stars": repo.get("stargazerCount", 0),
            "forks": repo.get("forkCount", 0),
            "primary_language": repo.get("primaryLanguage", {}).get("name"),
            "languages": {e.get("node", {}).get("name"): e.get("size") for e in languages},
            "topics": [t.get("topic", {}).get("name") for t in topics],
            "last_push": repo.get("pushedAt"),
            "contributor_count": repo.get("mentionableUsers", {}).get("totalCount", 0),
        }
