"""
Pydantic schemas for request and response validation.
"""

from datetime import datetime
from typing import Dict, List, Optional, Literal

from pydantic import BaseModel, EmailStr, Field, HttpUrl, ConfigDict


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    github_id: str
    github_username: str
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = None


class IssueFilterParams(BaseModel):
    difficulty: Optional[str] = None
    technology: Optional[str] = None
    language: Optional[str] = None
    repo_owner: Optional[str] = None
    issue_type: Optional[str] = None
    days_back: Optional[int] = Field(default=30)
    limit: int = Field(default=20, le=100)
    offset: int = Field(default=0, ge=0)


class IssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    url: str
    difficulty: Optional[str] = None
    issue_type: Optional[str] = None
    score: Optional[float] = None
    repo_owner: Optional[str] = None
    repo_name: Optional[str] = None
    repo_stars: Optional[int] = None
    issue_number: Optional[int] = None
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    repo_topics: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    is_bookmarked: bool = False


class IssueDetailResponse(IssueResponse):
    body: Optional[str] = None
    description: Optional[str] = None
    repo_url: Optional[str] = None
    repo_forks: Optional[int] = None
    time_estimate: Optional[str] = None
    contributor_count: Optional[int] = None
    is_active: bool = True


class IssueListResponse(BaseModel):
    issues: List[IssueResponse]
    total: int


class IssueDiscoverRequest(BaseModel):
    labels: Optional[List[str]] = None
    language: Optional[str] = None
    min_stars: Optional[int] = None
    limit: int = Field(default=25, le=100)
    apply_quality_filters: bool = True


class BookmarkRequest(BaseModel):
    issue_id: int


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    skills: List[str] = Field(default_factory=list)
    experience_level: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
    preferred_languages: List[str] = Field(default_factory=list)
    time_availability: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProfileUpdateRequest(BaseModel):
    skills: Optional[List[str]] = None
    experience_level: Optional[str] = None
    interests: Optional[List[str]] = None
    preferred_languages: Optional[List[str]] = None
    time_availability: Optional[int] = None


class ScoreBreakdownResponse(BaseModel):
    issue_id: int
    total_score: float
    breakdown: Dict[str, float] = Field(default_factory=dict)


class LabelRequest(BaseModel):
    label: str = Field(pattern="^(good|bad)$")


class ScoredIssueResponse(BaseModel):
    issue: IssueResponse
    score: float
    breakdown: Optional[Dict[str, float]] = None


class TopMatchesResponse(BaseModel):
    issues: List[IssueResponse]


class LabelStatusResponse(BaseModel):
    labeled_count: int
    good_count: int
    bad_count: int
    required: int = 200


class UnlabeledIssuesResponse(BaseModel):
    issues: List[IssueResponse]


class TrainModelRequest(BaseModel):
    model_type: Literal["logistic_regression", "xgboost"] = "logistic_regression"
    test_size: float = Field(default=0.2, ge=0.1, le=0.5)
    description: Optional[str] = None
    use_advanced: bool = True
    use_stacking: bool = False
    use_tuning: bool = False


class EvaluateModelRequest(BaseModel):
    model_type: Literal["logistic_regression", "xgboost"] = "logistic_regression"
    test_size: float = Field(default=0.2, ge=0.1, le=0.5)


class ModelInfoResponse(BaseModel):
    trained_at: Optional[datetime] = None
    model_type: str = "logistic_regression"
    metrics: Optional[Dict] = None
    model_path: Optional[str] = None
    training_samples: Optional[int] = None


class IssueStatsResponse(BaseModel):
    total: int = 0
    bookmarked: int = 0
    labeled: int = 0
    top_score: Optional[float] = None
    by_difficulty: Dict[str, int] = Field(default_factory=dict)


class JobInfo(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    next_run_time: Optional[str] = None
    trigger: str


class JobRunRequest(BaseModel):
    job_id: str
    user_id: Optional[int] = None


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
    notes: List[NoteResponse]
