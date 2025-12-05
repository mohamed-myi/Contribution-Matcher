"""
Background job functions for the internal scheduler.

Includes:
- Issue discovery
- Scoring
- Feature cache refresh
- ML training
- Security maintenance (token blacklist cleanup)
"""

from __future__ import annotations

import logging
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from core.repositories import TokenBlacklistRepository

from ..config import get_settings
from ..database import SessionLocal
from ..models import User
from ..schemas import IssueDiscoverRequest, TrainModelRequest
from ..services import feature_cache_service, issue_service, ml_service, scoring_service

logger = logging.getLogger("backend.scheduler.jobs")


def _get_users(db: Session, user_id: Optional[int]) -> Iterable[User]:
    if user_id:
        user = db.query(User).filter(User.id == user_id).one_or_none()
        if user:
            return [user]
        logger.warning("User %s not found for job", user_id)
        return []
    return db.query(User).all()


def run_issue_discovery_job(user_id: Optional[int] = None, limit: Optional[int] = None) -> None:
    settings = get_settings()
    limit = limit or settings.scheduler_discovery_limit
    with SessionLocal() as db:
        for user in _get_users(db, user_id):
            logger.info("Running discovery for user %s", user.id)
            request = IssueDiscoverRequest(limit=limit)
            issue_service.discover_issues_for_user(db, user, request)


def run_scoring_job(user_id: Optional[int] = None) -> None:
    with SessionLocal() as db:
        for user in _get_users(db, user_id):
            logger.info("Running scoring for user %s", user.id)
            scoring_service.score_all_issues(db, user)


def run_feature_refresh_job(user_id: Optional[int] = None) -> None:
    with SessionLocal() as db:
        for user in _get_users(db, user_id):
            logger.info("Refreshing feature cache for user %s", user.id)
            refreshed_user = db.query(User).filter(User.id == user.id).one()
            for issue in refreshed_user.issues:
                feature_cache_service.get_breakdown_and_features(db, refreshed_user, issue)


def run_ml_training_job(user_id: Optional[int] = None, model_type: str = "logistic_regression") -> None:
    with SessionLocal() as db:
        for user in _get_users(db, user_id):
            stats = ml_service.label_status(db, user)
            if stats["good"] < 1 or stats["bad"] < 1:
                logger.info("Skipping ML training for user %s; insufficient labels", user.id)
                continue
            logger.info("Training ML model (%s) for user %s", model_type, user.id)
            payload = TrainModelRequest(model_type=model_type)
            ml_service.train_model(db, user, payload)


# =============================================================================
# Security Maintenance Jobs
# =============================================================================

def run_token_blacklist_cleanup() -> None:
    """
    Clean up expired tokens from the blacklist table.
    
    This job should run periodically (e.g., hourly) to prevent the
    token_blacklist table from growing unbounded. Expired tokens are
    safe to delete since they can no longer be used anyway.
    
    Security Note:
    - Tokens are blacklisted on logout to prevent reuse before expiry
    - Once a token's expiry time has passed, it's invalid regardless
    - This cleanup is purely for database hygiene, not security-critical
    """
    with SessionLocal() as db:
        try:
            repo = TokenBlacklistRepository(db)
            deleted_count = repo.cleanup_expired()
            db.commit()
            
            if deleted_count > 0:
                logger.info(
                    "Token blacklist cleanup completed",
                    extra={"deleted_count": deleted_count}
                )
            else:
                logger.debug("Token blacklist cleanup: no expired tokens found")
                
        except Exception as e:
            logger.error(
                "Token blacklist cleanup failed",
                extra={"error": str(e)}
            )
            db.rollback()

