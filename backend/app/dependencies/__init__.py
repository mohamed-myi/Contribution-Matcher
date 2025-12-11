"""
FastAPI dependency injection module.

Provides centralized dependencies for:
- Database sessions
- Repositories
- Services
- Caching
"""

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from core.cache import cache
from core.db import db as core_db, get_db as core_get_db
from core.repositories import (
    IssueRepository,
    ProfileRepository,
    RepoMetadataRepository,
    TokenBlacklistRepository,
    UserRepository,
)
from core.services import ScoringService

from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models import User

# =============================================================================
# Repository Dependencies
# =============================================================================


def get_issue_repository(db: Session = Depends(get_db)) -> IssueRepository:
    """Get IssueRepository instance."""
    return IssueRepository(db)


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    """Get UserRepository instance."""
    return UserRepository(db)


def get_profile_repository(db: Session = Depends(get_db)) -> ProfileRepository:
    """Get ProfileRepository instance."""
    return ProfileRepository(db)


def get_repo_metadata_repository(db: Session = Depends(get_db)) -> RepoMetadataRepository:
    """Get RepoMetadataRepository instance."""
    return RepoMetadataRepository(db)


def get_token_blacklist_repository(db: Session = Depends(get_db)) -> TokenBlacklistRepository:
    """Get TokenBlacklistRepository instance."""
    return TokenBlacklistRepository(db)


# =============================================================================
# Service Dependencies
# =============================================================================


def get_scoring_service(
    issue_repo: IssueRepository = Depends(get_issue_repository),
) -> ScoringService:
    """Get ScoringService instance with injected repository."""
    return ScoringService(issue_repo)


# =============================================================================
# Cache Dependencies
# =============================================================================


def get_cache():
    """Get Redis cache instance."""
    if not cache.is_available:
        cache.initialize()
    return cache


# =============================================================================
# Combined Dependencies
# =============================================================================


class RequestContext:
    """
    Request context with commonly needed dependencies.

    Usage:
        @router.get("/endpoint")
        def endpoint(ctx: RequestContext = Depends(get_request_context)):
            issues = ctx.issue_repo.list_with_bookmarks(ctx.user.id, filters)
    """

    def __init__(
        self,
        db: Session,
        user: User,
        issue_repo: IssueRepository,
        profile_repo: ProfileRepository,
        scoring_service: ScoringService,
    ):
        self.db = db
        self.user = user
        self.issue_repo = issue_repo
        self.profile_repo = profile_repo
        self.scoring_service = scoring_service


def get_request_context(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    issue_repo: IssueRepository = Depends(get_issue_repository),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
    scoring_service: ScoringService = Depends(get_scoring_service),
) -> RequestContext:
    """Get full request context with all dependencies."""
    return RequestContext(
        db=db,
        user=current_user,
        issue_repo=issue_repo,
        profile_repo=profile_repo,
        scoring_service=scoring_service,
    )


__all__ = [
    # Repository dependencies
    "get_issue_repository",
    "get_user_repository",
    "get_profile_repository",
    "get_repo_metadata_repository",
    "get_token_blacklist_repository",
    # Service dependencies
    "get_scoring_service",
    # Cache dependencies
    "get_cache",
    # Combined dependencies
    "RequestContext",
    "get_request_context",
]
