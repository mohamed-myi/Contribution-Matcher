"""
Unified SQLAlchemy models for Contribution Matcher.

This package provides the single source of truth for all database models.
Both the CLI and backend use these shared models.

Usage:
    from core.models import User, Issue, DevProfile

    # Or import all
    from core.models import *
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
from .profile import DevProfile
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

