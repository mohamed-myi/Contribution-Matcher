"""Celery task definitions."""

from workers.tasks.discovery_tasks import (
    batch_discover_task,
    cleanup_stale_issues_task,
    discover_issues_task,
)
from workers.tasks.ml_tasks import (
    cleanup_old_models_task,
    evaluate_model_task,
    generate_embeddings_task,
    train_model_task,
)
from workers.tasks.scoring_tasks import (
    on_profile_update_task,
    recompute_all_scores_task,
    score_single_issue_task,
    score_user_issues_task,
)
from workers.tasks.staleness_tasks import (
    verify_all_users_issues_task,
    verify_single_issue_task,
    verify_stale_issues_task,
)

__all__ = [
    # Discovery
    "discover_issues_task",
    "cleanup_stale_issues_task",
    "batch_discover_task",
    # Scoring
    "score_user_issues_task",
    "score_single_issue_task",
    "recompute_all_scores_task",
    "on_profile_update_task",
    # ML
    "train_model_task",
    "evaluate_model_task",
    "generate_embeddings_task",
    "cleanup_old_models_task",
    # Staleness
    "verify_stale_issues_task",
    "verify_all_users_issues_task",
    "verify_single_issue_task",
]
