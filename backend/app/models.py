"""
SQLAlchemy ORM models for the Contribution Matcher backend.

This module provides backward compatibility with the existing backend code.
It re-exports all models from the unified core.models package.

For new code, prefer importing directly from core.models:
    from core.models import User, Issue, DevProfile
"""

# Re-export all models from core.models for backward compatibility
from core.models import (
    Base,
    DevProfile,
    Issue,
    IssueBookmark,
    IssueEmbedding,
    IssueFeatureCache,
    IssueLabel,
    IssueNote,
    IssueTechnology,
    RepoMetadata,
    TokenBlacklist,
    User,
    UserMLModel,
)

__all__ = [
    "Base",
    "User",
    "TokenBlacklist",
    "DevProfile",
    "Issue",
    "IssueTechnology",
    "IssueBookmark",
    "IssueLabel",
    "IssueEmbedding",
    "IssueFeatureCache",
    "IssueNote",
    "UserMLModel",
    "RepoMetadata",
]

