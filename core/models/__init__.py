"""
Unified SQLAlchemy models for Contribution Matcher.

Single source of truth for all database models. Used by both CLI and backend.

Usage:
    from core.models import User, Issue, DevProfile
"""

from .base import Base
from .issue import (
    Issue,
    IssueBookmark,
    IssueEmbedding,
    IssueFeatureCache,
    IssueLabel,
    IssueNote,
    IssueTechnology,
)
from .ml import UserMLModel
from .profile import (
    DevProfile,
    PROFILE_SOURCE_GITHUB,
    PROFILE_SOURCE_RESUME,
    PROFILE_SOURCE_MANUAL,
)
from .repo import RepoMetadata
from .user import TokenBlacklist, User

__all__ = [
    # Base
    "Base",
    # User
    "User",
    "TokenBlacklist",
    # Profile
    "DevProfile",
    "PROFILE_SOURCE_GITHUB",
    "PROFILE_SOURCE_RESUME",
    "PROFILE_SOURCE_MANUAL",
    # Issue
    "Issue",
    "IssueTechnology",
    "IssueBookmark",
    "IssueLabel",
    "IssueEmbedding",
    "IssueFeatureCache",
    "IssueNote",
    # ML
    "UserMLModel",
    # Repo
    "RepoMetadata",
]

