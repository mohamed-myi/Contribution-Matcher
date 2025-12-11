"""
Scoring service to compute profile-to-issue match scores with optional ML adjustment.
"""

from __future__ import annotations

from pathlib import Path

import joblib
from sqlalchemy.orm import Session

from ..models import Issue, User, UserMLModel
from ..schemas import IssueResponse, ScoreBreakdownResponse
from . import issue_service
from .feature_cache_service import get_breakdown_and_features


def _load_user_model(user: User, db: Session) -> tuple[UserMLModel, object] | None:
    """
    Load the most recent trained ML model for a user.

    Returns:
        Tuple of (UserMLModel record, loaded model) or None when unavailable.
    """
    record = (
        db.query(UserMLModel)
        .filter(UserMLModel.user_id == user.id)
        .order_by(UserMLModel.trained_at.desc())
        .first()
    )
    if not record or not record.model_path:
        return None
    model_path = Path(record.model_path)
    if not model_path.exists():
        return None
    try:
        model = joblib.load(model_path)
        return record, model
    except Exception:
        return None


def _ml_adjustment(model_tuple: tuple[UserMLModel, object] | None, features: list[float]) -> float:
    """
    Compute ML-based adjustment to the rule-based score.

    Args:
        model_tuple: Optional (record, model) tuple from _load_user_model.
        features: Feature vector for prediction.

    Returns:
        Adjustment value to apply to the total score.
    """
    if not model_tuple:
        return 0.0
    _, model = model_tuple
    try:
        proba = model.predict_proba([features])[0][1]
        adjustment = (proba - 0.5) * 15.0  # Range roughly -7.5 to +7.5
        return float(adjustment)
    except Exception:
        return 0.0


def score_issue(db: Session, user: User, issue: Issue) -> tuple[IssueResponse, float, dict]:
    """Score a single issue and return (issue_response, total_score, breakdown_dict)."""
    breakdown, features = get_breakdown_and_features(db, user, issue)
    model = _load_user_model(user, db)
    adjustment = _ml_adjustment(model, features)
    total_score = max(0.0, min(100.0, breakdown.total_score + adjustment))

    breakdown_dict = breakdown.to_dict()
    breakdown_dict["ml_adjustment"] = adjustment

    response_dict = issue_service.issue_to_response_dict(issue, user.id, db)
    response_dict["score"] = total_score
    issue_response = IssueResponse(**response_dict)
    return issue_response, total_score, breakdown_dict


def score_all_issues(db: Session, user: User) -> list[IssueResponse]:
    """Score all issues and return list of IssueResponses with scores."""
    issues = db.query(Issue).filter(Issue.user_id == user.id).all()
    results = []
    for idx, issue in enumerate(issues):
        try:
            issue_response, _, _ = score_issue(db, user, issue)
            results.append(issue_response)
        except Exception as e:
            raise
    return sorted(results, key=lambda r: r.score or 0, reverse=True)


def get_top_matches(db: Session, user: User, limit: int = 10) -> list[IssueResponse]:
    """Get top N matched issues."""
    try:
        all_scored = score_all_issues(db, user)
        result = all_scored[:limit]
        return result
    except Exception as e:
        raise


def get_score_for_issue(db: Session, user: User, issue_id: int) -> ScoreBreakdownResponse:
    """Get detailed score breakdown for a single issue."""
    issue = issue_service.get_issue(db, user, issue_id)
    _, total_score, breakdown_dict = score_issue(db, user, issue)

    return ScoreBreakdownResponse(
        issue_id=issue_id,
        total_score=total_score,
        breakdown=breakdown_dict,
    )
