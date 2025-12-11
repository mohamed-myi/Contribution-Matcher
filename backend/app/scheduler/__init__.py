"""
Scheduler initialization and management.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import get_settings
from . import jobs

logger = logging.getLogger("backend.scheduler")

JOB_DEFINITIONS = {
    "discover_all": {
        "func": jobs.run_issue_discovery_job,
        "description": "Discover new issues for all users",
    },
    "score_all": {
        "func": jobs.run_scoring_job,
        "description": "Score all issues for all users",
    },
    "refresh_features": {
        "func": jobs.run_feature_refresh_job,
        "description": "Refresh cached feature vectors",
    },
    "train_ml": {
        "func": jobs.run_ml_training_job,
        "description": "Train ML model for all users",
    },
    "cleanup_blacklist": {
        "func": jobs.run_token_blacklist_cleanup,
        "description": "Clean up expired tokens from blacklist (security maintenance)",
    },
}


def _build_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    jobstores = {
        "default": SQLAlchemyJobStore(url=settings.database_url),
    }
    scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")
    return scheduler


scheduler = _build_scheduler()


def _cron(trigger_str: str) -> CronTrigger:
    return CronTrigger.from_crontab(trigger_str)


def schedule_default_jobs() -> None:
    settings = get_settings()
    scheduler.add_job(
        jobs.run_issue_discovery_job,
        _cron(settings.scheduler_discovery_cron),
        id="discover_all",
        replace_existing=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        jobs.run_scoring_job,
        _cron(settings.scheduler_scoring_cron),
        id="score_all",
        replace_existing=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        jobs.run_ml_training_job,
        _cron(settings.scheduler_ml_cron),
        id="train_ml",
        replace_existing=True,
        misfire_grace_time=300,
    )
    # Security maintenance: clean up expired blacklisted tokens hourly
    scheduler.add_job(
        jobs.run_token_blacklist_cleanup,
        _cron("0 * * * *"),  # Every hour at minute 0
        id="cleanup_blacklist",
        replace_existing=True,
        misfire_grace_time=600,  # 10 minute grace period
    )


def start_scheduler() -> None:
    if scheduler.running:
        return
    schedule_default_jobs()
    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shut down")


def list_jobs() -> list[dict[str, Any]]:
    items = []
    for job in scheduler.get_jobs():
        items.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "description": JOB_DEFINITIONS.get(job.id, {}).get("description"),
            }
        )
    return items


def trigger_job(job_id: str, **kwargs) -> None:
    job_def = JOB_DEFINITIONS.get(job_id)
    if not job_def:
        raise ValueError(f"Unknown job_id: {job_id}")
    scheduler.add_job(
        job_def["func"],
        "date",
        run_date=datetime.now(timezone.utc),
        kwargs=kwargs,
    )


def reschedule_job(job_id: str, cron: str) -> None:
    trigger = _cron(cron)
    scheduler.reschedule_job(job_id, trigger=trigger)
