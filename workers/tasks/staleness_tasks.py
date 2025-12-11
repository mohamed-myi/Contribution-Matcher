"""
Background tasks for issue staleness verification.

Periodically checks GitHub to verify issue status and mark closed issues.
"""

from core.db import db
from core.logging import get_logger

from ..celery_app import celery_app

logger = get_logger("worker.staleness")


@celery_app.task(name="workers.tasks.staleness.verify_stale_issues")
def verify_stale_issues_task(
    user_id: int,
    limit: int = 50,
    min_age_days: int = 7,
) -> dict:
    """
    Background task to verify stale issues for a user.

    Args:
        user_id: User ID to verify issues for
        limit: Maximum number of issues to verify
        min_age_days: Only verify issues not checked in this many days

    Returns:
        Dict with verification summary
    """
    logger.info("staleness_task_started", user_id=user_id, limit=limit)

    try:
        with db.session() as session:
            from backend.app.services import staleness_service

            result = staleness_service.bulk_verify_issues(
                db=session,
                user_id=user_id,
                limit=limit,
                min_age_days=min_age_days,
            )

            logger.info(
                "staleness_task_complete",
                user_id=user_id,
                verified=result.get("verified", 0),
                closed=result.get("now_closed", 0),
            )

            return result

    except Exception as e:
        logger.error("staleness_task_failed", user_id=user_id, error=str(e))
        raise


@celery_app.task(name="workers.tasks.staleness.verify_all_users_issues")
def verify_all_users_issues_task(
    limit_per_user: int = 25,
    min_age_days: int = 7,
) -> dict:
    """
    Background task to verify stale issues for all users.

    Typically run as a scheduled job.

    Args:
        limit_per_user: Maximum issues to verify per user
        min_age_days: Only verify issues not checked in this many days

    Returns:
        Dict with overall summary
    """
    logger.info("bulk_staleness_task_started", limit_per_user=limit_per_user)

    try:
        with db.session() as session:
            from backend.app.models import User
            from backend.app.services import staleness_service

            # Get all users with active issues
            users = session.query(User).all()

            total_results = {
                "users_processed": 0,
                "total_verified": 0,
                "total_closed": 0,
                "total_errors": 0,
            }

            for user in users:
                result = staleness_service.bulk_verify_issues(
                    db=session,
                    user_id=user.id,
                    limit=limit_per_user,
                    min_age_days=min_age_days,
                )

                total_results["users_processed"] += 1
                total_results["total_verified"] += result.get("verified", 0)
                total_results["total_closed"] += result.get("now_closed", 0)
                total_results["total_errors"] += result.get("errors", 0)

            logger.info(
                "bulk_staleness_task_complete",
                users=total_results["users_processed"],
                verified=total_results["total_verified"],
                closed=total_results["total_closed"],
            )

            return total_results

    except Exception as e:
        logger.error("bulk_staleness_task_failed", error=str(e))
        raise


@celery_app.task(name="workers.tasks.staleness.verify_single_issue")
def verify_single_issue_task(user_id: int, issue_id: int) -> dict:
    """
    Background task to verify a single issue.

    Args:
        user_id: User ID
        issue_id: Issue ID to verify

    Returns:
        Dict with verification result
    """
    logger.info("single_issue_verify_started", user_id=user_id, issue_id=issue_id)

    try:
        with db.session() as session:
            from backend.app.services import staleness_service
            from core.repositories import IssueRepository

            repo = IssueRepository(session)
            issue = repo.get_by_id(issue_id, user_id)

            if not issue:
                return {"error": "Issue not found", "verified": False}

            result = staleness_service.verify_issue_status(session, issue)

            logger.info(
                "single_issue_verify_complete",
                issue_id=issue_id,
                status=result.get("status"),
            )

            return result

    except Exception as e:
        logger.error("single_issue_verify_failed", issue_id=issue_id, error=str(e))
        raise
