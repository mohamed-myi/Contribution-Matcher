"""
Shared utilities for computing issue/profile matching metrics.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.constants import (
    EXPERIENCE_MATCH_WEIGHT,
    FRESHNESS_WEIGHT,
    INTEREST_MATCH_WEIGHT,
    REPO_QUALITY_WEIGHT,
    SKILL_MATCH_WEIGHT,
    TIME_MATCH_WEIGHT,
)
from core.scoring.issue_scorer import (
    calculate_experience_match,
    calculate_freshness,
    calculate_interest_match,
    calculate_repo_quality,
    calculate_skill_match,
    calculate_time_match,
)

from ..models import DevProfile, Issue, User
from . import profile_service


def get_model_dir() -> Path:
    """Return the filesystem directory for storing trained ML models."""
    base = Path(os.getenv("CONTRIBUTION_MATCHER_MODEL_DIR", "models"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def ensure_profile(db: Session, user: User) -> DevProfile:
    """Fetch the user's profile or raise if it does not exist."""
    profile = profile_service.get_profile(db, user)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile not found. Create a profile before scoring issues.",
        )
    return profile


def issue_technologies(issue: Issue) -> List[str]:
    """Return technology names attached to an issue."""
    return [tech.technology for tech in issue.technologies]


def compute_breakdown_and_features(issue: Issue, profile: DevProfile) -> Tuple[dict, List[float]]:
    """
    Calculate rule-based breakdown scores and feature vector for scoring.

    Args:
        issue: Issue ORM object with metadata and technologies.
        profile: User profile used for matching.

    Returns:
        Tuple of (breakdown dict, feature vector list).
    """
    technologies = issue_technologies(issue)
    skills = profile.skills or []

    skill_match_pct, _, _ = calculate_skill_match(skills, technologies)
    experience_score = calculate_experience_match(
        profile.experience_level or "intermediate",
        issue.difficulty,
    )

    repo_metadata = {
        "stars": issue.repo_stars,
        "forks": issue.repo_forks,
        "last_commit_date": issue.last_commit_date,
        "contributor_count": issue.contributor_count,
    }
    repo_quality_score = calculate_repo_quality(repo_metadata)

    updated_at_iso = issue.updated_at.isoformat() if issue.updated_at else None
    freshness_score = calculate_freshness(updated_at_iso)

    time_match_score = calculate_time_match(
        profile.time_availability_hours_per_week,
        issue.time_estimate,
    )

    interest_match_score = calculate_interest_match(
        profile.interests or [],
        issue.repo_topics or [],
    )

    feature_vector = [
        skill_match_pct,
        experience_score,
        repo_quality_score,
        freshness_score,
        time_match_score,
        interest_match_score,
        float(issue.repo_stars or 0),
        float(issue.repo_forks or 0),
        float(issue.contributor_count or 0),
    ]

    skill_score = (skill_match_pct / 100.0) * SKILL_MATCH_WEIGHT
    total_score = (
        skill_score
        + experience_score
        + repo_quality_score
        + freshness_score
        + time_match_score
        + interest_match_score
    )

    breakdown = {
        "skill_match_pct": skill_match_pct,
        "experience_score": experience_score,
        "repo_quality_score": repo_quality_score,
        "freshness_score": freshness_score,
        "time_match_score": time_match_score,
        "interest_match_score": interest_match_score,
        "total_score": total_score,
    }

    return breakdown, feature_vector

