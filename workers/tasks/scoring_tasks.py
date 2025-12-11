"""
Issue scoring tasks.

These tasks handle:
- Scoring issues against user profiles
- Batch score updates with configurable batch sizes
- Feature cache warming
- Cache invalidation on profile changes

Queue: scoring (high priority, parallelized with multiple workers)

Performance optimizations:
- Batch sizes: 100-500 issues per batch
- Bulk DB operations to reduce roundtrips
- Pipeline Redis operations for cache updates
"""

from celery import group, shared_task
from celery.exceptions import MaxRetriesExceededError

from core.logging import get_logger

logger = get_logger("worker.scoring")

# Batch processing configuration
DEFAULT_BATCH_SIZE = 100
LARGE_BATCH_SIZE = 500
PARALLEL_BATCH_COUNT = 5  # Number of parallel batches


@shared_task(
    bind=True,
    name="workers.tasks.scoring_tasks.score_user_issues",
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=600,  # 10 minutes
    time_limit=900,  # 15 minutes
)
def score_user_issues_task(
    self,
    user_id: int,
    batch_size: int = 100,
) -> dict:
    """
    Score all active issues for a user.

    Updates the cached_score column for efficient retrieval.
    Invalidates user's cache after completion.

    Args:
        user_id: User ID to score issues for
        batch_size: Number of issues to process per batch

    Returns:
        Dictionary with scoring results
    """
    from core.cache import CacheKeys, cache
    from core.db import db
    from core.repositories import IssueRepository, ProfileRepository
    from core.services import ScoringService

    logger.info("scoring_started", user_id=user_id, batch_size=batch_size)

    try:
        with db.session() as session:
            # Get user profile
            profile_repo = ProfileRepository(session)
            profile = profile_repo.get_by_user_id(user_id)

            if not profile:
                logger.warning("scoring_no_profile", user_id=user_id)
                return {"scored": 0, "user_id": user_id, "error": "No profile"}

            profile_data = {
                "skills": profile.skills or [],
                "experience_level": profile.experience_level,
                "interests": profile.interests or [],
                "preferred_languages": profile.preferred_languages or [],
                "time_availability_hours_per_week": profile.time_availability_hours_per_week,
            }

            # Create scoring service with repository
            issue_repo = IssueRepository(session)
            scoring_service = ScoringService(issue_repo)

            # Batch score issues
            total_scored = scoring_service.batch_score_issues(
                user_id=user_id,
                profile=profile_data,
                batch_size=batch_size,
            )

        # Invalidate user cache
        cache.delete_pattern(CacheKeys.user_pattern(user_id))

        logger.info("scoring_complete", user_id=user_id, scored=total_scored)

        return {
            "scored": total_scored,
            "user_id": user_id,
        }

    except Exception as exc:
        logger.error("scoring_failed", user_id=user_id, error=str(exc))
        try:
            self.retry(exc=exc)
            return {"scored": 0, "user_id": user_id, "error": str(exc), "retrying": True}
        except MaxRetriesExceededError:
            return {"scored": 0, "user_id": user_id, "error": str(exc)}


@shared_task(
    bind=True,
    name="workers.tasks.scoring_tasks.score_single_issue",
    max_retries=2,
    soft_time_limit=30,
    time_limit=60,
)
def score_single_issue_task(
    self,
    user_id: int,
    issue_id: int,
) -> dict:
    """
    Score a single issue for a user.

    Useful for scoring newly discovered issues immediately.

    Args:
        user_id: User ID
        issue_id: Issue ID to score

    Returns:
        Dictionary with score result
    """
    from core.db import db
    from core.repositories import IssueRepository, ProfileRepository
    from core.services import ScoringService

    logger.debug("scoring_single_issue", issue_id=issue_id, user_id=user_id)

    try:
        with db.session() as session:
            # Get profile
            profile_repo = ProfileRepository(session)
            profile = profile_repo.get_by_user_id(user_id)

            if not profile:
                return {"score": None, "error": "No profile"}

            profile_data = {
                "skills": profile.skills or [],
                "experience_level": profile.experience_level,
                "interests": profile.interests or [],
                "preferred_languages": profile.preferred_languages or [],
                "time_availability_hours_per_week": profile.time_availability_hours_per_week,
            }

            # Get issue
            issue_repo = IssueRepository(session)
            issue = issue_repo.get_by_id(issue_id, user_id)

            if not issue:
                return {"score": None, "error": "Issue not found"}

            # Score the issue
            scoring_service = ScoringService(issue_repo)
            issue_dict = issue.to_dict()
            result = scoring_service.score_issue(issue_dict, profile_data)

            # Update cached score
            issue_repo.update_cached_scores({issue_id: result["total_score"]})

        return {
            "issue_id": issue_id,
            "score": result["total_score"],
            "user_id": user_id,
        }

    except Exception as exc:
        logger.error("scoring_single_failed", issue_id=issue_id, error=str(exc))
        try:
            self.retry(exc=exc)
            return {"score": None, "error": str(exc), "retrying": True}
        except MaxRetriesExceededError:
            return {"score": None, "error": str(exc)}


@shared_task(
    bind=True,
    name="workers.tasks.scoring_tasks.recompute_all_scores",
    max_retries=1,
    soft_time_limit=1800,  # 30 minutes
    time_limit=3600,  # 1 hour
)
def recompute_all_scores_task(
    self,
    user_ids: list[int] | None = None,
) -> dict:
    """
    Recompute scores for all users (or specific users).

    Triggered when:
    - ML model is retrained
    - Scoring algorithm changes
    - Scheduled periodic refresh

    Args:
        user_ids: Optional list of user IDs to recompute.
                  If None, recomputes for all users.

    Returns:
        Aggregated results
    """
    from core.db import db
    from core.models import User
    from core.services import ScoringService

    logger.info("recompute_all_started", user_ids=user_ids)

    try:
        # Invalidate ML model cache first (force reload)
        scoring_service = ScoringService()
        scoring_service.invalidate_model_cache()

        # Get user IDs if not provided
        if user_ids is None:
            with db.session() as session:
                users = session.query(User.id).all()
                user_ids = [u.id for u in users]

        results = []
        total_scored = 0

        for uid in user_ids:
            try:
                result = score_user_issues_task.apply(
                    args=[uid],
                    kwargs={"batch_size": 100},
                ).get(timeout=600)  # 10 min per user

                total_scored += result.get("scored", 0)
                results.append(result)

            except Exception as e:
                logger.warning("recompute_user_failed", user_id=uid, error=str(e))
                results.append({"user_id": uid, "error": str(e)})

        logger.info("recompute_all_complete", users=len(user_ids), total_scored=total_scored)

        return {
            "users_processed": len(user_ids),
            "total_scored": total_scored,
            "results": results,
        }

    except Exception as exc:
        logger.error("recompute_all_failed", error=str(exc))
        return {"error": str(exc)}


@shared_task(
    name="workers.tasks.scoring_tasks.on_profile_update",
)
def on_profile_update_task(user_id: int) -> dict:
    """
    Triggered when a user updates their profile.

    Invalidates caches and schedules score recomputation.
    """
    from core.cache import CacheKeys, cache

    logger.info("profile_updated_invalidating", user_id=user_id)

    # Invalidate user caches
    cache.delete_pattern(CacheKeys.user_pattern(user_id))

    # Schedule score recomputation (async)
    score_user_issues_task.delay(user_id)

    return {"user_id": user_id, "status": "recomputation_scheduled"}


@shared_task(
    bind=True,
    name="workers.tasks.scoring_tasks.warm_feature_cache",
    max_retries=2,
    soft_time_limit=300,  # 5 minutes
    time_limit=600,  # 10 minutes
)
def warm_feature_cache_task(
    self,
    user_id: int,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict:
    """
    Pre-compute and cache feature vectors for scoring.

    Warms the feature cache for a user's issues to speed up
    subsequent scoring operations.

    Args:
        user_id: User ID
        batch_size: Number of issues per batch

    Returns:
        Dictionary with warming results
    """
    from core.db import db
    from core.models import Issue, IssueFeatureCache
    from core.repositories import ProfileRepository

    logger.info("feature_cache_warming_started", user_id=user_id)

    try:
        with db.session() as session:
            # Get profile
            profile_repo = ProfileRepository(session)
            profile = profile_repo.get_by_user_id(user_id)

            if not profile:
                return {"warmed": 0, "error": "No profile"}

            profile_updated_at = profile.updated_at

            # Get issues without cached features or with stale cache
            issues = (
                session.query(Issue)
                .outerjoin(IssueFeatureCache, Issue.id == IssueFeatureCache.issue_id)
                .filter(
                    Issue.user_id == user_id,
                    Issue.is_active,
                )
                .filter(
                    # No cache or cache is stale (profile updated after cache)
                    (IssueFeatureCache.id.is_(None))  # type: ignore[attr-defined]
                    | (IssueFeatureCache.profile_updated_at < profile_updated_at)  # type: ignore[operator]
                )
                .limit(batch_size)
                .all()
            )

            if not issues:
                logger.info("feature_cache_already_warm", user_id=user_id)
                return {"warmed": 0, "user_id": user_id, "status": "already_warm"}

            # Pre-compute features
            from core.scoring.ml_trainer import extract_features

            profile_data = {
                "skills": profile.skills or [],
                "experience_level": profile.experience_level,
                "interests": profile.interests or [],
                "preferred_languages": profile.preferred_languages or [],
                "time_availability_hours_per_week": profile.time_availability_hours_per_week,
            }

            warmed_count = 0
            for issue in issues:
                try:
                    issue_dict = issue.to_dict()
                    features = extract_features(
                        issue_dict,
                        profile_data,
                        use_advanced=False,  # Base features only for cache
                        session=session,
                    )

                    # Store in feature cache
                    existing_cache = (
                        session.query(IssueFeatureCache)
                        .filter(IssueFeatureCache.issue_id == issue.id)
                        .first()
                    )

                    if existing_cache:
                        existing_cache.feature_vector = {"base": features}
                        existing_cache.profile_updated_at = profile_updated_at
                        existing_cache.issue_updated_at = issue.updated_at
                    else:
                        cache_entry = IssueFeatureCache(
                            issue_id=issue.id,
                            profile_updated_at=profile_updated_at,
                            issue_updated_at=issue.updated_at,
                            feature_vector={"base": features},
                        )
                        session.add(cache_entry)

                    warmed_count += 1

                except Exception as e:
                    logger.warning("feature_cache_issue_failed", issue_id=issue.id, error=str(e))

            session.flush()

        logger.info("feature_cache_warming_complete", user_id=user_id, warmed=warmed_count)

        return {
            "warmed": warmed_count,
            "user_id": user_id,
        }

    except Exception as exc:
        logger.error("feature_cache_warming_failed", user_id=user_id, error=str(exc))
        try:
            self.retry(exc=exc)
            return {"warmed": 0, "error": str(exc), "retrying": True}
        except MaxRetriesExceededError:
            return {"warmed": 0, "error": str(exc)}


@shared_task(
    bind=True,
    name="workers.tasks.scoring_tasks.batch_score_parallel",
    max_retries=1,
    soft_time_limit=1800,  # 30 minutes
    time_limit=3600,  # 1 hour
)
def batch_score_parallel_task(
    self,
    user_id: int,
    total_issues: int = 10000,
) -> dict:
    """
    Score large numbers of issues in parallel batches.

    Divides work into multiple parallel batches for faster processing.
    Useful for initial scoring of 10K+ issues.

    Args:
        user_id: User ID
        total_issues: Total number of issues to score

    Returns:
        Aggregated results from all batches
    """
    from core.db import db
    from core.models import Issue

    logger.info("batch_score_parallel_started", user_id=user_id, total=total_issues)

    try:
        # Count actual issues
        with db.session() as session:
            actual_count = (
                session.query(Issue)
                .filter(
                    Issue.user_id == user_id,
                    Issue.is_active,
                )
                .count()
            )

        total_to_process = min(total_issues, actual_count)
        batch_size = max(100, total_to_process // PARALLEL_BATCH_COUNT)

        # Create parallel tasks
        batch_tasks = []
        for offset in range(0, total_to_process, batch_size):
            batch_tasks.append(
                score_user_issues_task.si(
                    user_id,
                    batch_size=min(batch_size, total_to_process - offset),
                )
            )

        if not batch_tasks:
            return {"scored": 0, "batches": 0}

        # Execute in parallel using group
        job = group(batch_tasks)
        result = job.apply_async()

        # Wait for all to complete
        all_results = result.get(timeout=1800)

        total_scored = sum(r.get("scored", 0) for r in all_results if isinstance(r, dict))

        logger.info(
            "batch_score_parallel_complete",
            user_id=user_id,
            batches=len(batch_tasks),
            total_scored=total_scored,
        )

        return {
            "scored": total_scored,
            "batches": len(batch_tasks),
            "results": all_results,
        }

    except Exception as exc:
        logger.error("batch_score_parallel_failed", user_id=user_id, error=str(exc))
        return {"error": str(exc)}
