"""
Shared Pydantic Types/Schemas.

API contracts shared between frontend and backend.
These schemas define the shape of data exchanged via the API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl

from .enums import DifficultyLevel, ExperienceLevel, IssueLabel, IssueType


# =============================================================================
# Pagination
# =============================================================================

class PaginationParams(BaseModel):
    """Standard pagination parameters."""
    offset: int = Field(default=0, ge=0, description="Number of items to skip")
    limit: int = Field(default=20, ge=1, le=100, description="Number of items to return")


class PaginatedResponse(BaseModel):
    """Base model for paginated responses."""
    total: int = Field(description="Total number of items")
    offset: int = Field(description="Current offset")
    limit: int = Field(description="Current limit")
    has_more: bool = Field(description="Whether more items exist")


# =============================================================================
# Issue Types
# =============================================================================

class IssueBase(BaseModel):
    """Base issue fields."""
    title: str = Field(min_length=1, max_length=512)
    url: str = Field(min_length=1, max_length=512)
    body: Optional[str] = None
    repo_owner: Optional[str] = None
    repo_name: Optional[str] = None
    repo_url: Optional[str] = None
    difficulty: Optional[DifficultyLevel] = None
    issue_type: Optional[IssueType] = None
    time_estimate: Optional[str] = None
    labels: Optional[List[str]] = None
    repo_stars: Optional[int] = None
    repo_forks: Optional[int] = None
    repo_languages: Optional[Dict[str, int]] = None
    repo_topics: Optional[List[str]] = None


class IssueCreate(IssueBase):
    """Schema for creating an issue."""
    technologies: Optional[List[tuple[str, Optional[str]]]] = None


class IssueResponse(IssueBase):
    """Schema for issue response."""
    id: int
    is_active: bool = True
    is_bookmarked: bool = False
    cached_score: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    technologies: List[str] = []

    class Config:
        from_attributes = True


class IssueListResponse(PaginatedResponse):
    """Paginated list of issues."""
    items: List[IssueResponse]


class IssueScoreResponse(BaseModel):
    """Issue with detailed score breakdown."""
    issue_id: int
    issue_title: str
    repo_name: Optional[str] = None
    url: str
    score: float = Field(ge=0, le=100)
    breakdown: Dict[str, Any]


# =============================================================================
# Profile Types
# =============================================================================

class ProfileBase(BaseModel):
    """Base profile fields."""
    skills: List[str] = Field(default_factory=list)
    experience_level: ExperienceLevel = ExperienceLevel.INTERMEDIATE
    interests: List[str] = Field(default_factory=list)
    preferred_languages: List[str] = Field(default_factory=list)
    time_availability_hours_per_week: Optional[int] = Field(default=None, ge=1, le=168)


class ProfileCreate(ProfileBase):
    """Schema for creating/updating a profile."""
    pass


class ProfileResponse(ProfileBase):
    """Schema for profile response."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    source: Optional[str] = None

    class Config:
        from_attributes = True


class ProfileFromGitHub(BaseModel):
    """Schema for creating profile from GitHub username."""
    username: str = Field(min_length=1, max_length=39)


class ProfileFromResume(BaseModel):
    """Schema for creating profile from resume file."""
    # File is handled separately via form data
    pass


# =============================================================================
# Scoring Types
# =============================================================================

class ScoringRequest(BaseModel):
    """Request for scoring issues."""
    profile_id: Optional[int] = None
    issue_ids: Optional[List[int]] = None
    limit: int = Field(default=10, ge=1, le=100)
    use_ml: bool = True


class ScoringResponse(BaseModel):
    """Response containing scored issues."""
    scores: List[IssueScoreResponse]
    profile_used: bool
    ml_model_used: bool


class TopMatchesResponse(BaseModel):
    """Response for top matches endpoint."""
    matches: List[IssueScoreResponse]
    total_scored: int
    profile_id: Optional[int] = None


# =============================================================================
# ML Types
# =============================================================================

class LabelIssueRequest(BaseModel):
    """Request for labeling an issue."""
    issue_id: int
    label: IssueLabel


class TrainingStatusResponse(BaseModel):
    """ML training status response."""
    task_id: Optional[str] = None
    status: str
    progress: Optional[float] = None
    metrics: Optional[Dict[str, float]] = None
    error: Optional[str] = None


class ModelInfoResponse(BaseModel):
    """ML model information."""
    model_type: str
    version: str
    trained_at: Optional[datetime] = None
    metrics: Dict[str, float]
    sample_count: int


# =============================================================================
# Health/Status Types
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(description="Service status: healthy, degraded, unhealthy")
    version: str = Field(description="API version")
    database: Dict[str, Any] = Field(description="Database health status")
    cache: Dict[str, Any] = Field(description="Cache health status")
    uptime_seconds: float = Field(description="Service uptime in seconds")


class TaskStatusResponse(BaseModel):
    """Celery task status response."""
    task_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None


# =============================================================================
# Discovery Types
# =============================================================================

class DiscoveryRequest(BaseModel):
    """Request for discovering new issues."""
    labels: Optional[List[str]] = None
    language: Optional[str] = None
    min_stars: Optional[int] = Field(default=None, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class DiscoveryResponse(BaseModel):
    """Response from issue discovery."""
    task_id: Optional[str] = None
    discovered_count: int
    new_count: int
    status: str


# =============================================================================
# User Types
# =============================================================================

class UserResponse(BaseModel):
    """User response schema."""
    id: int
    github_id: str
    github_username: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
