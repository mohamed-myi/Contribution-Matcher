"""
Feature cache service for computing and caching issue scoring breakdowns.

Provides:
- Score breakdown computation for issues
- Feature extraction for ML training
- Caching layer for expensive computations
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from core.scoring.issue_scorer import get_match_breakdown
from core.scoring.ml_trainer import extract_base_features

from ..models import DevProfile, Issue, User
from . import profile_service

# Default model directory for user ML models
DEFAULT_MODEL_DIR = Path("models/users")


@dataclass
class ScoreBreakdown:
    """Score breakdown result with component scores."""

    skill_match_pct: float
    experience_score: float
    repo_quality_score: float
    freshness_score: float
    time_match_score: float
    interest_match_score: float
    total_score: float
    raw_breakdown: dict

    def to_dict(self) -> dict:
        """Convert breakdown to dictionary representation."""
        return {
            "skill_match_pct": self.skill_match_pct,
            "experience_score": self.experience_score,
            "repo_quality_score": self.repo_quality_score,
            "freshness_score": self.freshness_score,
            "time_match_score": self.time_match_score,
            "interest_match_score": self.interest_match_score,
            "total_score": self.total_score,
            **self.raw_breakdown,
        }


def get_model_dir() -> Path:
    """
    Get the directory path for storing user ML models.

    Creates the directory if it doesn't exist.

    Returns:
        Path to the model directory.
    """
    model_dir = DEFAULT_MODEL_DIR
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


def _profile_to_dict(profile: DevProfile | None) -> dict:
    """
    Convert a DevProfile to a dictionary format suitable for scoring.

    Args:
        profile: DevProfile ORM object or None.

    Returns:
        Dictionary with profile data for scoring functions.
    """
    if not profile:
        return {
            "skills": [],
            "experience_level": "intermediate",
            "interests": [],
            "time_availability_hours_per_week": 10,
        }

    return {
        "skills": profile.skills or [],
        "experience_level": profile.experience_level or "intermediate",
        "interests": profile.interests or [],
        "time_availability_hours_per_week": profile.time_availability_hours_per_week or 10,
        "preferred_languages": profile.preferred_languages or [],
    }


def _issue_to_dict(issue: Issue) -> dict:
    """
    Convert an Issue ORM object to a dictionary format suitable for scoring.

    Args:
        issue: Issue ORM object.

    Returns:
        Dictionary with issue data for scoring functions.
    """
    return {
        "id": issue.id,
        "title": issue.title,
        "body": issue.body,
        "url": issue.url,
        "repo_owner": issue.repo_owner,
        "repo_name": issue.repo_name,
        "repo_url": issue.repo_url,
        "difficulty": issue.difficulty,
        "issue_type": issue.issue_type,
        "time_estimate": issue.time_estimate,
        "labels": issue.labels or [],
        "repo_stars": issue.repo_stars,
        "repo_forks": issue.repo_forks,
        "repo_languages": issue.repo_languages,
        "repo_topics": issue.repo_topics or [],
        "last_commit_date": issue.last_commit_date,
        "contributor_count": issue.contributor_count,
        "is_active": issue.is_active,
        "created_at": issue.created_at,
        "updated_at": issue.updated_at,
    }


def get_breakdown_and_features(
    db: Session,
    user: User,
    issue: Issue,
) -> tuple[ScoreBreakdown, list[float]]:
    """
    Compute score breakdown and ML features for an issue.

    This function:
    1. Loads the user's profile
    2. Computes the match breakdown between profile and issue
    3. Extracts numerical features for ML training

    Args:
        db: Database session.
        user: User for whom to compute the score.
        issue: Issue to score.

    Returns:
        Tuple of (ScoreBreakdown, feature_list) where feature_list is suitable
        for ML model training.
    """
    # Get user's profile
    profile = profile_service.get_profile(db, user)
    profile_dict = _profile_to_dict(profile)

    # Convert issue to dict for scoring functions
    issue_dict = _issue_to_dict(issue)

    # Compute match breakdown
    try:
        raw_breakdown = get_match_breakdown(profile_dict, issue_dict, session=db)
    except Exception as e:
        raise

    # Extract component scores
    skills = raw_breakdown.get("skills", {})
    skill_match_pct = skills.get("match_percentage", 0.0)

    experience = raw_breakdown.get("experience", {})
    experience_score = experience.get("score", 0.0)

    repo_quality = raw_breakdown.get("repo_quality", {})
    repo_quality_score = repo_quality.get("score", 0.0)

    freshness = raw_breakdown.get("freshness", {})
    freshness_score = freshness.get("score", 0.0)

    time_match = raw_breakdown.get("time_match", {})
    time_match_score = time_match.get("score", 0.0)

    interest_match = raw_breakdown.get("interest_match", {})
    interest_match_score = interest_match.get("score", 0.0)

    # Compute total score using weights from constants
    from core.constants import (
        SKILL_MATCH_WEIGHT,
    )

    skill_weighted = (skill_match_pct / 100.0) * SKILL_MATCH_WEIGHT
    total_score = (
        skill_weighted
        + experience_score
        + repo_quality_score
        + freshness_score
        + time_match_score
        + interest_match_score
    )

    breakdown = ScoreBreakdown(
        skill_match_pct=skill_match_pct,
        experience_score=experience_score,
        repo_quality_score=repo_quality_score,
        freshness_score=freshness_score,
        time_match_score=time_match_score,
        interest_match_score=interest_match_score,
        total_score=total_score,
        raw_breakdown=raw_breakdown,
    )

    # Extract features for ML training
    try:
        features = extract_base_features(issue_dict, profile_dict, session=db)
    except Exception as e:
        raise

    return breakdown, features


def invalidate_cache(user_id: int, issue_id: int | None = None) -> None:
    """
    Invalidate cached scores for a user or specific issue.

    This is a placeholder for future Redis-based caching.
    Currently a no-op since we compute on demand.

    Args:
        user_id: User ID to invalidate cache for.
        issue_id: Optional specific issue ID to invalidate.
    """
    # TODO: Implement Redis-based cache invalidation when caching is added
    pass
