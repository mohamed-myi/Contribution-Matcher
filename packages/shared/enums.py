"""
Shared Enumerations.

Defines enums used across all packages for type safety and consistency.
"""

from enum import Enum


class ExperienceLevel(str, Enum):
    """Developer experience level."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class DifficultyLevel(str, Enum):
    """Issue difficulty level."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class IssueType(str, Enum):
    """Issue category type."""
    BUG = "bug"
    FEATURE = "feature"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    REFACTORING = "refactoring"
    ENHANCEMENT = "enhancement"
    QUESTION = "question"
    OTHER = "other"


class IssueLabel(str, Enum):
    """User-provided issue quality label for ML training."""
    GOOD = "good"
    BAD = "bad"


class IssueState(str, Enum):
    """GitHub issue state."""
    OPEN = "open"
    CLOSED = "closed"


class ProfileSource(str, Enum):
    """Source of profile data."""
    GITHUB = "github"
    RESUME = "resume"
    MANUAL = "manual"


class TaskStatus(str, Enum):
    """Celery task status."""
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    REVOKED = "REVOKED"
