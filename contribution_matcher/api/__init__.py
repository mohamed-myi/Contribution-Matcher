"""GitHub API integration module."""

from .github_api import (
    get_repo_metadata_from_api,
    search_issues,
)

__all__ = [
    "search_issues",
    "get_repo_metadata_from_api",
]

