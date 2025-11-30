"""
Feature caching for issue/profile combinations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from ..models import DevProfile, Issue, IssueFeatureCache, User
from . import matching_service


@dataclass
class BreakdownResult:
    """Internal breakdown result with individual score components."""
    issue_id: int
    total_score: float
    skill_match: float
    experience_match: float
    repo_quality: float
    freshness: float
    time_match: float
    interest_match: float
    ml_adjustment: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "skill_match": self.skill_match,
            "experience_match": self.experience_match,
            "repo_quality": self.repo_quality,
            "freshness": self.freshness,
            "time_match": self.time_match,
            "interest_match": self.interest_match,
            "ml_adjustment": self.ml_adjustment,
        }


def _breakdown_from_cache(issue: Issue, cache: IssueFeatureCache) -> BreakdownResult:
    return BreakdownResult(
        issue_id=issue.id,
        total_score=cache.total_score or 0,
        skill_match=cache.skill_match_pct or 0,
        experience_match=cache.experience_score or 0,
        repo_quality=cache.repo_quality_score or 0,
        freshness=cache.freshness_score or 0,
        time_match=cache.time_match_score or 0,
        interest_match=cache.interest_match_score or 0,
        ml_adjustment=0.0,
    )


def _feature_vector_from_cache(cache: IssueFeatureCache) -> List[float]:
    if not cache.feature_vector:
        return []
    if isinstance(cache.feature_vector, list):
        return [float(x) for x in cache.feature_vector]
    return [float(x) for x in json.loads(cache.feature_vector)]


def _store_cache(
    db: Session,
    issue: Issue,
    profile: DevProfile,
    breakdown: BreakdownResult,
    feature_vector: List[float],
) -> None:
    cache = (
        db.query(IssueFeatureCache)
        .filter(IssueFeatureCache.issue_id == issue.id)
        .one_or_none()
    )
    data = {
        "issue_id": issue.id,
        "profile_updated_at": profile.updated_at,
        "issue_updated_at": issue.updated_at,
        "computed_at": datetime.utcnow(),
        "skill_match_pct": breakdown.skill_match,
        "experience_score": breakdown.experience_match,
        "repo_quality_score": breakdown.repo_quality,
        "freshness_score": breakdown.freshness,
        "time_match_score": breakdown.time_match,
        "interest_match_score": breakdown.interest_match,
        "total_score": breakdown.total_score,
        "feature_vector": feature_vector,
    }
    if cache:
        for key, value in data.items():
            setattr(cache, key, value)
    else:
        cache = IssueFeatureCache(**data)
        db.add(cache)
    db.commit()


def get_breakdown_and_features(
    db: Session,
    user: User,
    issue: Issue,
) -> Tuple[BreakdownResult, List[float]]:
    profile = matching_service.ensure_profile(db, user)
    cache = (
        db.query(IssueFeatureCache)
        .filter(IssueFeatureCache.issue_id == issue.id)
        .one_or_none()
    )
    cache_valid = False
    if cache:
        profile_fresh = (
            not profile.updated_at
            or not cache.profile_updated_at
            or cache.profile_updated_at >= profile.updated_at
        )
        issue_fresh = (
            not issue.updated_at
            or not cache.issue_updated_at
            or cache.issue_updated_at >= issue.updated_at
        )
        cache_valid = profile_fresh and issue_fresh

    if cache and cache_valid:
        breakdown = _breakdown_from_cache(issue, cache)
        features = _feature_vector_from_cache(cache)
        return breakdown, features

    breakdown_dict, feature_vector = matching_service.compute_breakdown_and_features(issue, profile)
    breakdown = BreakdownResult(
        issue_id=issue.id,
        total_score=breakdown_dict["total_score"],
        skill_match=breakdown_dict["skill_match_pct"],
        experience_match=breakdown_dict["experience_score"],
        repo_quality=breakdown_dict["repo_quality_score"],
        freshness=breakdown_dict["freshness_score"],
        time_match=breakdown_dict["time_match_score"],
        interest_match=breakdown_dict["interest_match_score"],
        ml_adjustment=0.0,
    )
    _store_cache(db, issue, profile, breakdown, feature_vector)
    return breakdown, feature_vector
