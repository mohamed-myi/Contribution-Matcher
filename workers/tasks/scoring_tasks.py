"""
Issue scoring tasks.

These tasks handle:
- Scoring issues against user profiles
- Batch score updates
- Cache invalidation on profile changes

Queue: scoring (parallelized with multiple workers)
"""

from typing import Dict, List, Optional

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from core.logging import get_logger

logger = get_logger("worker.scoring")


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
) -> Dict:
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
    from core.db import db
    from core.repositories import IssueRepository, ProfileRepository
    from core.services import ScoringService
    from core.cache import cache, CacheKeys
    
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
) -> Dict:
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
    user_ids: Optional[List[int]] = None,
) -> Dict:
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
def on_profile_update_task(user_id: int) -> Dict:
    """
    Triggered when a user updates their profile.
    
    Invalidates caches and schedules score recomputation.
    """
    from core.cache import cache, CacheKeys
    
    logger.info("profile_updated_invalidating", user_id=user_id)
    
    # Invalidate user caches
    cache.delete_pattern(CacheKeys.user_pattern(user_id))
    
    # Schedule score recomputation (async)
    score_user_issues_task.delay(user_id)
    
    return {"user_id": user_id, "status": "recomputation_scheduled"}

