"""
Shared Package.

Contains types, constants, utilities, and API contracts shared
across all packages (api, worker, web).

Usage:
    from packages.shared import IssueSchema, ProfileSchema
    from packages.shared.constants import TECHNOLOGY_FAMILIES
"""

from packages.shared.types import (
    IssueCreate,
    IssueResponse,
    IssueListResponse,
    ProfileCreate,
    ProfileResponse,
    ScoringRequest,
    ScoringResponse,
    HealthResponse,
    PaginationParams,
)
from packages.shared.constants import (
    EXPERIENCE_LEVELS,
    DIFFICULTY_LEVELS,
    ISSUE_TYPES,
    TECHNOLOGY_FAMILIES,
    TECHNOLOGY_SYNONYMS,
)
from packages.shared.enums import (
    ExperienceLevel,
    DifficultyLevel,
    IssueType,
    IssueLabel,
)

__all__ = [
    # Types
    "IssueCreate",
    "IssueResponse",
    "IssueListResponse",
    "ProfileCreate",
    "ProfileResponse",
    "ScoringRequest",
    "ScoringResponse",
    "HealthResponse",
    "PaginationParams",
    # Constants
    "EXPERIENCE_LEVELS",
    "DIFFICULTY_LEVELS",
    "ISSUE_TYPES",
    "TECHNOLOGY_FAMILIES",
    "TECHNOLOGY_SYNONYMS",
    # Enums
    "ExperienceLevel",
    "DifficultyLevel",
    "IssueType",
    "IssueLabel",
]
