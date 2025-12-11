"""
GitHub Module.

Provides async GitHub API client with:
- GraphQL queries for efficient data fetching
- Rate limiting and backoff strategies
- Connection pooling for parallel requests
"""

# Use lazy imports to avoid requiring aiohttp at import time
def __getattr__(name):
    if name == "GitHubStreamClient":
        from .client import GitHubStreamClient
        return GitHubStreamClient
    elif name == "RateLimiter":
        from .client import RateLimiter
        return RateLimiter
    elif name == "SEARCH_ISSUES_QUERY":
        from .queries import SEARCH_ISSUES_QUERY
        return SEARCH_ISSUES_QUERY
    elif name == "GET_ISSUE_DETAILS_QUERY":
        from .queries import GET_ISSUE_DETAILS_QUERY
        return GET_ISSUE_DETAILS_QUERY
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "GitHubStreamClient",
    "RateLimiter",
    "SEARCH_ISSUES_QUERY",
    "GET_ISSUE_DETAILS_QUERY",
]
