"""
GitHub Service - Enforces efficient batch patterns for GitHub API access.

Key optimizations:
1. Batch metadata fetching via GraphQL (1 call instead of 5 per repo)
2. Redis-backed rate limit tracking across workers
3. Automatic retry with exponential backoff
4. Request deduplication within discovery sessions
"""

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from core.cache import CacheKeys, cache
from core.config import get_settings
from core.constants import DISCOVERY_LABELS
from core.logging import get_logger

logger = get_logger("github.service")


@dataclass
class RateLimitInfo:
    """GitHub API rate limit information."""

    remaining: int
    limit: int
    reset_at: datetime

    @property
    def is_low(self) -> bool:
        """Check if remaining allowance is below 10%."""
        return self.remaining < (self.limit * 0.1)

    @property
    def seconds_until_reset(self) -> int:
        """Return seconds until the GitHub rate limit resets."""
        reset_at = self.reset_at
        if reset_at.tzinfo is None:
            reset_at = reset_at.replace(tzinfo=timezone.utc)
        else:
            reset_at = reset_at.astimezone(timezone.utc)
        delta = reset_at - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds()))

    def to_dict(self) -> dict:
        return {
            "remaining": self.remaining,
            "limit": self.limit,
            "reset_at": self.reset_at.isoformat(),
            "is_low": self.is_low,
        }


class GitHubService:
    """
    High-level GitHub API service with enforced batch patterns.

    Usage:
        service = GitHubService()

        # Discover issues with automatic batch optimization
        issues = service.discover_issues(
            labels=["good first issue"],
            language="python",
            limit=50,
        )
    """

    def __init__(self):
        self.settings = get_settings()
        self._seen_repos: set[tuple[str, str]] = set()
        self._repo_cache: dict[tuple[str, str], dict] = {}

    # Rate Limit Management

    def get_rate_limit(self) -> RateLimitInfo | None:
        """
        Get current GitHub rate limit status using cache, then API as fallback.

        Returns:
            RateLimitInfo if retrieved, otherwise None when API/cache are unavailable.
        """
        # Try cache first
        cached = cache.get_json(CacheKeys.GITHUB_RATE_LIMIT)
        if cached:
            return RateLimitInfo(
                remaining=cached["remaining"],
                limit=cached["limit"],
                reset_at=datetime.fromisoformat(cached["reset_at"]),
            )

        # Fetch from API
        from core.api.github_api import GITHUB_API_BASE, _make_request

        response = _make_request(f"{GITHUB_API_BASE}/rate_limit")
        if response:
            data = response.json()
            core = data.get("resources", {}).get("core", {})

            info = RateLimitInfo(
                remaining=core.get("remaining", 5000),
                limit=core.get("limit", 5000),
                reset_at=datetime.fromtimestamp(core.get("reset", 0), tz=timezone.utc),
            )

            # Cache for 1 minute
            cache.set_json(CacheKeys.GITHUB_RATE_LIMIT, info.to_dict(), ttl=60)

            return info

        return None

    def update_rate_limit(self, remaining: int, reset_timestamp: int) -> None:
        """
        Persist the most recent rate limit values in Redis cache.

        Args:
            remaining: Requests remaining in the current window.
            reset_timestamp: Unix timestamp when the window resets.
        """
        info = RateLimitInfo(
            remaining=remaining,
            limit=5000,  # Default
            reset_at=datetime.fromtimestamp(reset_timestamp, tz=timezone.utc),
        )
        cache.set_json(CacheKeys.GITHUB_RATE_LIMIT, info.to_dict(), ttl=60)

    def wait_for_rate_limit(self, max_wait: int = 300) -> bool:
        """
        Wait for the rate limit window to reset when nearing exhaustion.

        Args:
            max_wait: Maximum seconds to pause before aborting.

        Returns:
            True when it is safe to proceed; False if waiting would exceed max_wait.
        """
        info = self.get_rate_limit()
        if not info or not info.is_low:
            return True

        wait_time = min(info.seconds_until_reset, max_wait)
        if wait_time > max_wait:
            logger.warning(
                "rate_limit_exceeded",
                remaining=info.remaining,
                reset_seconds=info.seconds_until_reset,
                max_wait=max_wait,
            )
            return False

        if wait_time > 0:
            logger.info("rate_limit_wait", wait_seconds=wait_time)
            time.sleep(wait_time)

        return True

    # Batch Discovery (Enforced Pattern)

    def discover_issues(
        self,
        labels: list[str] | None = None,
        language: str | None = None,
        min_stars: int = 10,
        limit: int = 50,
    ) -> list[dict]:
        """
        Discover issues using a batch-first workflow to minimize GitHub API calls.

        Args:
            labels: Optional list of labels to filter by.
            language: Optional primary language filter.
            min_stars: Minimum stars a repository must have to be included.
            limit: Maximum number of issues to return.

        Returns:
            List of parsed issue dictionaries enriched with repository metadata.
        """
        from core.api.github_api import batch_get_repo_metadata, search_issues
        from core.parsing.issue_parser import parse_issue
        from core.parsing.quality_checker import check_issue_quality

        labels = labels or DISCOVERY_LABELS[:5]

        logger.info(
            "discover_started",
            labels=labels[:3],
            language=language,
            min_stars=min_stars,
            limit=limit,
        )

        # Check rate limit before starting
        if not self.wait_for_rate_limit():
            logger.warning("discover_aborted_rate_limit")
            return []

        # Step 1: Search for issues
        raw_issues = search_issues(
            labels=labels,
            language=language,
            min_stars=min_stars,
            limit=limit,
            apply_quality_filters=True,
        )

        if not raw_issues:
            logger.info("discover_no_results")
            return []

        logger.info("search_complete", raw_count=len(raw_issues))

        # Step 2: Collect unique repos
        repos_to_fetch: set[tuple[str, str]] = set()
        issue_repo_map: dict[str, tuple[str, str]] = {}

        for issue in raw_issues:
            repo_url = issue.get("repository_url", "")
            if repo_url:
                parts = repo_url.replace("https://api.github.com/repos/", "").split("/")
                if len(parts) >= 2:
                    repo_key = (parts[0], parts[1])
                    issue_url = issue.get("html_url", "")
                    issue_repo_map[issue_url] = repo_key

                    # Only fetch if not already cached in this session
                    if repo_key not in self._repo_cache:
                        repos_to_fetch.add(repo_key)

        # Step 3: Batch fetch metadata (single GraphQL call)
        if repos_to_fetch:
            logger.info("batch_fetch_metadata", repo_count=len(repos_to_fetch))

            metadata_results = batch_get_repo_metadata(
                list(repos_to_fetch),
                use_cache=True,
                use_graphql=True,
            )

            # Update session cache
            self._repo_cache.update(metadata_results)

        # Step 4: Parse issues with metadata
        parsed_issues = []

        for issue in raw_issues:
            issue_url = issue.get("html_url", "")
            repo_key = issue_repo_map.get(issue_url)
            repo_metadata = self._repo_cache.get(repo_key) if repo_key else None

            # Quality check
            is_valid, quality_issues = check_issue_quality(issue, repo_metadata)
            if not is_valid:
                logger.debug(
                    "issue_filtered",
                    url=issue_url,
                    reasons=quality_issues,
                )
                continue

            # Parse with metadata
            try:
                parsed = parse_issue(issue, repo_metadata)
                if parsed:
                    parsed_issues.append(parsed)
            except Exception as e:
                logger.warning(
                    "parse_failed",
                    url=issue_url,
                    error=str(e),
                )

        logger.info(
            "discover_complete",
            raw_count=len(raw_issues),
            parsed_count=len(parsed_issues),
            repos_fetched=len(repos_to_fetch),
        )

        return parsed_issues

    # Batch Status Check

    def batch_check_status(
        self,
        issue_urls: list[str],
        chunk_size: int = 50,
    ) -> dict[str, str]:
        """
        Fetch issue states in batches via GitHub GraphQL.

        Args:
            issue_urls: GitHub issue URLs to check.
            chunk_size: Maximum number of issues per GraphQL query.

        Returns:
            Mapping of issue URL to status value ('open', 'closed', or 'unknown').
        """
        import requests  # type: ignore[import-untyped]

        from core.api.github_api import GITHUB_GRAPHQL_ENDPOINT, _get_headers

        def _get_graphql_headers():
            return _get_headers(graphql=True)

        results = {}

        # Parse issue URLs into (owner, repo, number) tuples
        issues_to_check = []
        for url in issue_urls:
            try:
                parts = url.replace("https://github.com/", "").split("/")
                if len(parts) >= 4 and parts[2] == "issues":
                    issues_to_check.append(
                        {
                            "url": url,
                            "owner": parts[0],
                            "repo": parts[1],
                            "number": int(parts[3]),
                        }
                    )
            except (ValueError, IndexError):
                results[url] = "unknown"

        # Batch query via GraphQL
        for chunk_start in range(0, len(issues_to_check), chunk_size):
            chunk = issues_to_check[chunk_start : chunk_start + chunk_size]

            # Build GraphQL query
            query_parts = []
            for i, issue_info in enumerate(chunk):
                alias = f"issue_{i}"
                query_parts.append(
                    f"""
                    {alias}: repository(owner: "{issue_info["owner"]}", name: "{issue_info["repo"]}") {{
                        issue(number: {issue_info["number"]}) {{
                            state
                        }}
                    }}
                """
                )

            query = "query { " + " ".join(query_parts) + " }"

            try:
                response = requests.post(
                    GITHUB_GRAPHQL_ENDPOINT,
                    headers=_get_graphql_headers(),
                    json={"query": query},
                    timeout=30,
                )

                if response.status_code == 200:
                    data = response.json().get("data", {})

                    for i, issue_info in enumerate(chunk):
                        alias = f"issue_{i}"
                        repo_data = data.get(alias, {})
                        issue_data = repo_data.get("issue", {}) if repo_data else {}
                        state = str(issue_data.get("state", "")).lower() if issue_data else ""

                        issue_url = str(issue_info.get("url", ""))
                        results[issue_url] = state if state else "unknown"
                else:
                    logger.warning(
                        "graphql_status_check_failed",
                        status=response.status_code,
                    )
                    for issue_info in chunk:
                        issue_url = str(issue_info.get("url", ""))
                        results[issue_url] = "unknown"

            except Exception as e:
                logger.error("status_check_error", error=str(e))
                for issue_info in chunk:
                    issue_url = str(issue_info.get("url", ""))
                    results[issue_url] = "unknown"

            # Small delay between chunks
            if chunk_start + chunk_size < len(issues_to_check):
                time.sleep(0.2)

        return results

    # GraphQL Repository Query

    def graphql_get_repos(
        self,
        repo_list: list[tuple[str, str]],
    ) -> dict[tuple[str, str], dict]:
        """
        Fetch multiple repositories via a single GraphQL query.

        Args:
            repo_list: List of (owner, repo) tuples to retrieve.

        Returns:
            Mapping of (owner, repo) to repository metadata.
        """
        from core.api.github_api import _graphql_batch_fetch_repos

        # Use existing GraphQL batch function
        results = _graphql_batch_fetch_repos(repo_list)
        # Filter out None values to match return type
        return {k: v for k, v in results.items() if v is not None}  # type: ignore[return-value]

    # Session Management

    def clear_session_cache(self) -> None:
        """Clear session-level repository caches for the service instance."""
        self._seen_repos.clear()
        self._repo_cache.clear()

    def get_session_stats(self) -> dict[str, Any]:
        """
        Summarize current session cache usage.

        Returns:
            Dictionary with counts of cached and seen repositories.
        """
        return {
            "cached_repos": len(self._repo_cache),
            "seen_repos": len(self._seen_repos),
        }


# Singleton instance
_github_service: GitHubService | None = None


def get_github_service() -> GitHubService:
    """
    Retrieve the shared GitHubService instance.

    Returns:
        GitHubService singleton.
    """
    global _github_service
    if _github_service is None:
        _github_service = GitHubService()
    return _github_service
