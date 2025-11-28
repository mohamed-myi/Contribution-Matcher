"""Issue scoring and ML training module."""

from .issue_scorer import (
    calculate_experience_match,
    calculate_freshness,
    calculate_interest_match,
    calculate_repo_quality,
    calculate_skill_match,
    calculate_time_match,
    get_match_breakdown,
    get_top_matches,
    score_issue_against_profile,
    score_profile_against_all_issues,
)
from .ml_trainer import (
    extract_features,
    load_labeled_issues,
    predict_issue_quality,
    train_model,
)

__all__ = [
    "score_issue_against_profile",
    "score_profile_against_all_issues",
    "get_top_matches",
    "get_match_breakdown",
    "calculate_skill_match",
    "calculate_experience_match",
    "calculate_repo_quality",
    "calculate_freshness",
    "calculate_time_match",
    "calculate_interest_match",
    "train_model",
    "predict_issue_quality",
    "extract_features",
    "load_labeled_issues",
]

