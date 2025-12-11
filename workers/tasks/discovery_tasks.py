"""
GitHub issue discovery tasks.

These tasks handle:
- Searching GitHub for new issues
- Fetching repository metadata
- Cleaning up stale/closed issues

Rate Limited: 10 requests per minute to respect GitHub API limits.
"""

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from core.logging import get_logger

logger = get_logger("worker.discovery")


@shared_task(
    bind=True,
    name="workers.tasks.discovery_tasks.discover_issues",
    rate_limit="10/m",  # 10 per minute (GitHub API friendly)
    max_retries=3,
    default_retry_delay=60,  # 1 minute
    soft_time_limit=300,  # 5 minutes
    time_limit=600,  # 10 minutes
)
def discover_issues_task(
    self,
    user_id: int,
    labels: list[str] | None = None,
    language: str | None = None,
    limit: int = 50,
) -> dict:
    """
    Discover new GitHub issues for a user.

    Uses GitHubService with enforced batch pattern:
    1. Search issues
    2. Batch fetch repo metadata (single GraphQL call)
    3. Parse and store

    Args:
        user_id: User ID to discover issues for
        labels: Optional list of labels to filter by
        language: Optional programming language to filter by
        limit: Maximum number of issues to discover

    Returns:
        Dictionary with discovery results
    """
    from core.db import db
    from core.repositories import IssueRepository
    from core.services import get_github_service

    logger.info(
        "discovery_started",
        user_id=user_id,
        labels=labels,
        language=language,
        limit=limit,
    )

    try:
        # Use GitHubService for optimized batch fetching
        github = get_github_service()

        parsed_issues = github.discover_issues(
            labels=labels or ["good first issue", "help wanted"],
            language=language,
            limit=limit,
        )

        if not parsed_issues:
            logger.info("discovery_no_results", user_id=user_id)
            return {"discovered": 0, "user_id": user_id}

        # Bulk upsert to database
        with db.session() as session:
            repo = IssueRepository(session)
            repo.bulk_upsert(user_id, parsed_issues)

        # Get session stats
        stats = github.get_session_stats()

        logger.info(
            "discovery_complete",
            user_id=user_id,
            discovered=len(parsed_issues),
            cached_repos=stats["cached_repos"],
        )

        return {
            "discovered": len(parsed_issues),
            "user_id": user_id,
            "labels": labels,
            "language": language,
            "repos_cached": stats["cached_repos"],
        }

    except Exception as exc:
        logger.error(
            "discovery_failed",
            user_id=user_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error("discovery_max_retries", user_id=user_id)
            return {"discovered": 0, "user_id": user_id, "error": str(exc)}


@shared_task(
    bind=True,
    name="workers.tasks.discovery_tasks.cleanup_stale_issues",
    rate_limit="5/m",  # Slower rate limit for cleanup
    max_retries=2,
    soft_time_limit=180,
    time_limit=300,
)
def cleanup_stale_issues_task(
    self,
    user_id: int,
    limit: int = 50,
) -> dict:
    """
    Check and mark closed issues as inactive using batch GraphQL queries.

    Args:
        user_id: User ID to cleanup issues for
        limit: Maximum number of issues to check

    Returns:
        Dictionary with cleanup results
    """
    from core.db import db
    from core.repositories import IssueRepository
    from core.services import get_github_service

    logger.info("cleanup_started", user_id=user_id, limit=limit)

    try:
        # Get active issue URLs
        with db.session() as session:
            repo = IssueRepository(session)
            active_issues = repo.get_active_issue_urls(user_id, limit=limit)

        if not active_issues:
            logger.info("cleanup_no_active_issues", user_id=user_id)
            return {"marked_inactive": 0, "user_id": user_id}

        # Batch check status via GraphQL
        github = get_github_service()
        statuses = github.batch_check_status(active_issues)

        # Find closed issues
        closed_urls = [url for url, status in statuses.items() if status == "closed"]

        # Mark as inactive
        marked_count = 0
        if closed_urls:
            with db.session() as session:
                repo = IssueRepository(session)
                marked_count = repo.mark_inactive(closed_urls)

        logger.info(
            "cleanup_complete",
            checked=len(active_issues),
            closed=len(closed_urls),
            marked_inactive=marked_count,
        )

        return {
            "checked": len(active_issues),
            "marked_inactive": marked_count,
            "user_id": user_id,
        }

    except Exception as exc:
        logger.error("cleanup_failed", error=str(exc))
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"marked_inactive": 0, "error": str(exc)}


@shared_task(
    bind=True,
    name="workers.tasks.discovery_tasks.batch_discover",
    max_retries=1,
    soft_time_limit=900,  # 15 minutes
    time_limit=1200,  # 20 minutes
)
def batch_discover_task(
    self,
    user_id: int,
    strategies: list[dict] | None = None,
) -> dict:
    """
    Run multiple discovery strategies in sequence.

    Args:
        user_id: User ID
        strategies: List of discovery configs, e.g.:
            [
                {"labels": ["good first issue"], "limit": 15},
                {"labels": ["help wanted"], "limit": 15},
                {"language": "python", "limit": 10},
            ]

    Returns:
        Aggregated results from all strategies
    """
    if strategies is None:
        strategies = [
            {"labels": ["good first issue", "beginner-friendly"], "limit": 15},
            {"labels": ["help wanted", "contributions welcome"], "limit": 15},
            {"language": "python", "limit": 10},
            {"language": "javascript", "limit": 10},
        ]

    logger.info(
        "batch_discovery_started",
        user_id=user_id,
        strategy_count=len(strategies),
    )

    total_discovered = 0
    results = []

    for strategy in strategies:
        try:
            # Run discovery synchronously within this task
            result = discover_issues_task.apply(
                args=[user_id],
                kwargs=strategy,
            ).get(timeout=300)  # 5 min timeout per strategy

            total_discovered += result.get("discovered", 0)
            results.append(result)

        except Exception as e:
            logger.warning(
                "strategy_failed",
                strategy=strategy,
                error=str(e),
            )
            results.append({"error": str(e), **strategy})

    # Run cleanup at the end
    try:
        cleanup_result = cleanup_stale_issues_task.apply(
            args=[user_id],
            kwargs={"limit": 30},
        ).get(timeout=180)
        results.append(cleanup_result)
    except Exception as e:
        logger.warning("batch_cleanup_failed", error=str(e))

    logger.info(
        "batch_discovery_complete",
        user_id=user_id,
        total_discovered=total_discovered,
    )

    return {
        "user_id": user_id,
        "total_discovered": total_discovered,
        "strategies_run": len(strategies),
        "results": results,
    }
