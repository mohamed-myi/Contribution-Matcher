"""
Celery Beat schedule configuration.

Defines periodic tasks for:
- Daily issue discovery
- Periodic score recomputation
- Weekly model retraining
- Cleanup tasks
"""

from celery.schedules import crontab

from core.config import get_settings

settings = get_settings()


def get_beat_schedule():
    """
    Get the Celery Beat schedule configuration.

    Schedule is configurable via environment variables.

    Returns:
        Dictionary of scheduled tasks
    """
    return {
        # Discovery Tasks (Daily)
        "discover-issues-daily": {
            "task": "workers.tasks.discovery_tasks.batch_discover",
            "schedule": crontab(
                hour=6,  # 6 AM UTC
                minute=0,
            ),
            "args": [],
            "kwargs": {
                "user_id": 1,  # Default user (override in production)
                "strategies": [
                    {"labels": ["good first issue", "beginner-friendly"], "limit": 15},
                    {"labels": ["help wanted", "contributions welcome"], "limit": 15},
                    {"language": "python", "limit": 10},
                    {"language": "javascript", "limit": 10},
                    {"language": "typescript", "limit": 10},
                ],
            },
            "options": {"queue": "discovery"},
        },
        # Cleanup Tasks (Daily)
        "cleanup-stale-issues-daily": {
            "task": "workers.tasks.discovery_tasks.cleanup_stale_issues",
            "schedule": crontab(
                hour=5,  # 5 AM UTC (before discovery)
                minute=0,
            ),
            "args": [1],  # user_id
            "kwargs": {"limit": 50},
            "options": {"queue": "discovery"},
        },
        # Scoring Tasks (After Discovery)
        "recompute-scores-daily": {
            "task": "workers.tasks.scoring_tasks.score_user_issues",
            "schedule": crontab(
                hour=7,  # 7 AM UTC (after discovery)
                minute=0,
            ),
            "args": [1],  # user_id
            "kwargs": {"batch_size": 100},
            "options": {"queue": "scoring"},
        },
        # ML Tasks (Weekly)
        "train-model-weekly": {
            "task": "workers.tasks.ml_tasks.train_model",
            "schedule": crontab(
                hour=2,  # 2 AM UTC Sunday
                minute=0,
                day_of_week=0,  # Sunday
            ),
            "args": [],
            "kwargs": {
                "model_type": "xgboost",
                "use_hyperopt": False,  # Quick training
            },
            "options": {"queue": "ml"},
        },
        "generate-embeddings-daily": {
            "task": "workers.tasks.ml_tasks.generate_embeddings",
            "schedule": crontab(
                hour=4,  # 4 AM UTC
                minute=0,
            ),
            "args": [],
            "kwargs": {"batch_size": 50},
            "options": {"queue": "ml"},
        },
        # Maintenance Tasks (Weekly)
        "cleanup-old-models-weekly": {
            "task": "workers.tasks.ml_tasks.cleanup_old_models",
            "schedule": crontab(
                hour=3,  # 3 AM UTC Sunday
                minute=0,
                day_of_week=0,
            ),
            "args": [],
            "kwargs": {"keep_versions": 3},
            "options": {"queue": "ml"},
        },
    }


def apply_beat_schedule(celery_app):
    """
    Apply the beat schedule to a Celery app.

    Args:
        celery_app: Celery application instance
    """
    if settings.enable_scheduler:
        celery_app.conf.beat_schedule = get_beat_schedule()
        celery_app.conf.beat_schedule_filename = "celerybeat-schedule"
