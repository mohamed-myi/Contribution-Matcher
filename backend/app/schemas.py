"""
Pydantic schemas for request and response validation.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    github_id: str
    github_username: str
    email: EmailStr | None = None
    avatar_url: str | None = None


class IssueFilterParams(BaseModel):
    difficulty: str | None = None
    technology: str | None = None
    language: str | None = None
    repo_owner: str | None = None
    issue_type: str | None = None
    days_back: int | None = Field(default=30)
    limit: int = Field(default=20, le=100)
    offset: int = Field(default=0, ge=0)


class IssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    url: str
    difficulty: str | None = None
    issue_type: str | None = None
    score: float | None = None
    repo_owner: str | None = None
    repo_name: str | None = None
    repo_stars: int | None = None
    repo_languages: dict | None = None
    issue_number: int | None = None
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    repo_topics: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    is_bookmarked: bool = False
    # Staleness fields
    last_verified_at: datetime | None = None
    closed_at: datetime | None = None
    close_reason: str | None = None
    github_state: str | None = None
    is_stale: bool = False
    is_very_stale: bool = False


class IssueDetailResponse(IssueResponse):
    body: str | None = None
    description: str | None = None
    repo_url: str | None = None
    repo_forks: int | None = None
    time_estimate: str | None = None
    contributor_count: int | None = None
    is_active: bool = True


class IssueListResponse(BaseModel):
    issues: list[IssueResponse]
    total: int


class IssueDiscoverRequest(BaseModel):
    labels: list[str] | None = None
    language: str | None = None
    min_stars: int | None = None
    limit: int = Field(default=25, le=100)
    apply_quality_filters: bool = True


class BookmarkRequest(BaseModel):
    issue_id: int


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    skills: list[str] = Field(default_factory=list)
    experience_level: str | None = None
    interests: list[str] = Field(default_factory=list)
    preferred_languages: list[str] = Field(default_factory=list)
    time_availability: int | None = None
    profile_source: str = Field(
        default="manual", description="Origin of profile: github, resume, or manual"
    )
    last_github_sync: datetime | None = Field(
        default=None, description="Timestamp of last GitHub sync"
    )
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProfileSourceInfo(BaseModel):
    """Detailed information about profile source for UI display."""

    source: str = Field(description="Profile source: github, resume, or manual")
    is_from_github: bool = Field(default=False)
    is_from_resume: bool = Field(default=False)
    is_manual: bool = Field(default=True)
    last_github_sync: datetime | None = None
    can_resync_github: bool = Field(
        default=True, description="Whether user can re-sync from GitHub"
    )


class ProfileUpdateRequest(BaseModel):
    skills: list[str] | None = None
    experience_level: str | None = None
    interests: list[str] | None = None
    preferred_languages: list[str] | None = None
    time_availability: int | None = None


class ScoreBreakdownResponse(BaseModel):
    issue_id: int
    total_score: float
    breakdown: dict[str, Any] = Field(default_factory=dict)


class LabelRequest(BaseModel):
    label: str = Field(pattern="^(good|bad)$")


class ScoredIssueResponse(BaseModel):
    issue: IssueResponse
    score: float
    breakdown: dict[str, float] | None = None


class TopMatchesResponse(BaseModel):
    issues: list[IssueResponse]


class LabelStatusResponse(BaseModel):
    labeled_count: int
    good_count: int
    bad_count: int
    required: int = 200


class UnlabeledIssuesResponse(BaseModel):
    issues: list[IssueResponse]


class LabeledIssueResponse(BaseModel):
    """Issue with its label for the labeled issues management page."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    url: str
    difficulty: str | None = None
    issue_type: str | None = None
    repo_owner: str | None = None
    repo_name: str | None = None
    repo_stars: int | None = None
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    label: str  # "good" or "bad"
    labeled_at: datetime | None = None


class LabeledIssuesResponse(BaseModel):
    """Response for labeled issues list."""

    issues: list[LabeledIssueResponse]
    total: int
    good_count: int
    bad_count: int


class TrainModelRequest(BaseModel):
    model_type: Literal["logistic_regression", "xgboost"] = "logistic_regression"
    test_size: float = Field(default=0.2, ge=0.1, le=0.5)
    description: str | None = None
    use_advanced: bool = True
    use_stacking: bool = False
    use_tuning: bool = False


class EvaluateModelRequest(BaseModel):
    model_type: Literal["logistic_regression", "xgboost"] = "logistic_regression"
    test_size: float = Field(default=0.2, ge=0.1, le=0.5)


class ModelInfoResponse(BaseModel):
    trained_at: datetime | None = None
    model_type: str = "logistic_regression"
    metrics: dict | None = None
    model_path: str | None = None
    training_samples: int | None = None


class IssueStatsResponse(BaseModel):
    total: int = 0
    bookmarked: int = 0
    labeled: int = 0
    top_score: float | None = None
    by_difficulty: dict[str, int] = Field(default_factory=dict)


class JobInfo(BaseModel):
    id: str
    name: str | None = None
    description: str | None = None
    next_run_time: str | None = None
    trigger: str


class JobRunRequest(BaseModel):
    job_id: str
    user_id: int | None = None


class JobRescheduleRequest(BaseModel):
    job_id: str
    cron: str


class NoteCreateRequest(BaseModel):
    content: str


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    content: str
    created_at: datetime
    updated_at: datetime


class NotesListResponse(BaseModel):
    notes: list[NoteResponse]
