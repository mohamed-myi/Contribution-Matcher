"""
Celery task definitions.

Tasks are organized by function:
- discovery_tasks: GitHub issue discovery
- scoring_tasks: Issue scoring against profiles
- ml_tasks: ML model training
"""

from workers.tasks.discovery_tasks import (
    discover_issues_task,
    cleanup_stale_issues_task,
    batch_discover_task,
)
from workers.tasks.scoring_tasks import (
    score_user_issues_task,
    score_single_issue_task,
    recompute_all_scores_task,
)
from workers.tasks.ml_tasks import (
    train_model_task,
    evaluate_model_task,
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
    # ML
    "train_model_task",
    "evaluate_model_task",
]

