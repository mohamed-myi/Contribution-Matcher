"""
Repository pattern implementations for data access.

Repositories provide a clean abstraction over database operations,
with batch operations and efficient queries.

Usage:
    from core.repositories import IssueRepository
    from core.db import db

    with db.session() as session:
        repo = IssueRepository(session)
        issues, total, bookmarks = repo.list_with_bookmarks(user_id, filters)
"""

from .base import BaseRepository
from .issue_repository import IssueRepository
from .profile_repository import ProfileRepository
from .repo_metadata_repository import RepoMetadataRepository
from .user_repository import TokenBlacklistRepository, UserRepository

# Alias for compatibility with scoring tasks
DevProfileRepository = ProfileRepository

__all__ = [
    "BaseRepository",
    "IssueRepository",
    "UserRepository",
    "TokenBlacklistRepository",
    "ProfileRepository",
    "DevProfileRepository",  # Alias
    "RepoMetadataRepository",
]
