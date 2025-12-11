"""
Issue discovery and management endpoints.

Uses core repositories and services for database access.
"""

import csv
import io
import json
from enum import Enum
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.cache import CacheKeys, cache
from core.repositories import IssueRepository, ProfileRepository
from core.services import ScoringService

from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models import IssueBookmark, IssueLabel, IssueNote, User
from ..schemas import (
    IssueDetailResponse,
    IssueDiscoverRequest,
    IssueListResponse,
    IssueResponse,
    IssueStatsResponse,
    NoteCreateRequest,
    NoteResponse,
    NotesListResponse,
)
from ..services import issue_service

router = APIRouter(prefix="/issues", tags=["issues"])


# =============================================================================
# Filter Parameter Validation Enums
# =============================================================================


class DifficultyFilter(str, Enum):
    """Valid difficulty filter values."""

    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class IssueTypeFilter(str, Enum):
    """Valid issue type filter values."""

    bug = "bug"
    feature = "feature"
    documentation = "documentation"
    testing = "testing"
    refactoring = "refactoring"
    enhancement = "enhancement"


class ScoreRangeFilter(str, Enum):
    """Valid score range filter values."""

    high = "high"  # 80+
    medium = "medium"  # 50-79
    low = "low"  # <50


class OrderByFilter(str, Enum):
    """Valid order_by filter values."""

    created_at = "created_at"
    score = "score"
    repo_stars = "repo_stars"
    title = "title"


# =============================================================================
# Discovery Endpoints
# =============================================================================


@router.post("/discover", response_model=IssueListResponse)
def discover_issues(
    request: IssueDiscoverRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Discover issues from GitHub and store them."""
    issues = issue_service.discover_issues_for_user(db, current_user, request)
    return IssueListResponse(
        issues=[IssueResponse(**issue_service.issue_to_dict(i)) for i in issues],
        total=len(issues),
    )


@router.post("/discover/async")
def discover_issues_async(
    request: IssueDiscoverRequest,
    current_user: User = Depends(get_current_user),
):
    """Asynchronous issue discovery using Celery."""
    try:
        from workers.tasks import discover_issues_task

        task = discover_issues_task.delay(
            user_id=current_user.id,
            labels=request.labels,
            language=request.language,
            limit=request.limit,
        )

        return {
            "task_id": task.id,
            "status": "queued",
            "message": "Discovery task queued. Check /tasks/{task_id} for status.",
        }
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Celery workers not available. Use synchronous discovery.",
        )


@router.get("/discover/task/{task_id}")
def get_discovery_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """Check status of an async discovery task."""
    try:
        from workers.celery_app import celery_app

        result = celery_app.AsyncResult(task_id)
        response = {"task_id": task_id, "status": result.status}

        if result.ready():
            if result.successful():
                response["result"] = result.result
            else:
                response["error"] = str(result.result)

        return response
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Celery not available"
        )


# =============================================================================
# List & Query Endpoints
# =============================================================================


@router.get("", response_model=IssueListResponse)
def list_issues(
    difficulty: DifficultyFilter | None = Query(None, description="Filter by difficulty level"),
    technology: str | None = Query(None, description="Filter by technology"),
    language: str | None = Query(None, description="Filter by programming language"),
    repo_owner: str | None = Query(None, description="Filter by repository owner"),
    issue_type: IssueTypeFilter | None = Query(None, description="Filter by issue type"),
    days_back: int | None = Query(
        None, ge=1, le=365, description="Filter issues created within N days"
    ),
    min_stars: int | None = Query(None, ge=0, le=1000000, description="Minimum repository stars"),
    score_range: ScoreRangeFilter | None = Query(
        None, description="Score range: 'high' (80+), 'medium' (50-79), 'low' (<50)"
    ),
    limit: int = Query(20, ge=1, le=100, description="Number of results per page"),
    offset: int = Query(0, ge=0, le=10000, description="Pagination offset"),
    order_by: OrderByFilter = Query(OrderByFilter.created_at, description="Sort field"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List issues with filtering and pagination."""
    filters = {
        "difficulty": difficulty.value if difficulty else None,
        "technology": technology,
        "language": language,
        "repo_owner": repo_owner,
        "issue_type": issue_type.value if issue_type else None,
        "days_back": days_back,
        "min_stars": min_stars,
        "score_range": score_range.value if score_range else None,
        "order_by": order_by.value,
        "is_active": True,
    }

    repo = IssueRepository(db)
    issues, total, bookmarked_ids = repo.list_with_bookmarks(
        user_id=current_user.id,
        filters=filters,
        offset=offset,
        limit=limit,
    )

    # Use batch serialization to avoid N+1 queries
    issue_dicts = issue_service.batch_issue_to_dict(issues, bookmarked_ids)
    issue_responses = [IssueResponse(**d) for d in issue_dicts]

    return IssueListResponse(issues=issue_responses, total=total)


@router.get("/bookmarks", response_model=IssueListResponse)
def get_bookmarks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all bookmarked issues."""
    issues = issue_service.get_bookmarks(db, current_user)
    return IssueListResponse(
        issues=[IssueResponse(**issue_service.issue_to_dict(i, True)) for i in issues],
        total=len(issues),
    )


@router.get("/top-matches")
def get_top_matches(
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get top matching issues based on profile."""
    profile_repo = ProfileRepository(db)
    profile = profile_repo.get_by_user_id(current_user.id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile required for matching. Create a profile first.",
        )

    profile_data = {
        "skills": profile.skills or [],
        "experience_level": profile.experience_level,
        "interests": profile.interests or [],
        "preferred_languages": profile.preferred_languages or [],
        "time_availability_hours_per_week": profile.time_availability_hours_per_week,
    }

    issue_repo = IssueRepository(db)
    scoring_service = ScoringService(issue_repo)

    try:
        top_matches = scoring_service.get_top_matches(
            user_id=current_user.id,
            profile=profile_data,
            limit=limit,
        )
        return {"matches": top_matches, "total": len(top_matches)}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/stats", response_model=IssueStatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get issue statistics (cached for 5 minutes)."""
    cache_key = CacheKeys.user_stats(current_user.id)

    # Try to get from cache
    try:
        cached_stats = cache.get_json(cache_key)
        if cached_stats is not None:
            return IssueStatsResponse(**cached_stats)
    except Exception:
        pass

    # Compute stats
    try:
        repo = IssueRepository(db)
        stats = repo.get_variety_stats(current_user.id)

        labeled_count = db.query(IssueLabel).filter(IssueLabel.user_id == current_user.id).count()
        bookmark_count = (
            db.query(IssueBookmark).filter(IssueBookmark.user_id == current_user.id).count()
        )

        result = {
            "total": stats.get("total", 0),
            "bookmarked": bookmark_count,
            "labeled": labeled_count,
            "top_score": None,
            "by_difficulty": stats.get("by_difficulty", {}),
        }

        # Cache for 5 minutes
        cache.set_json(cache_key, result, CacheKeys.TTL_SHORT)
        return IssueStatsResponse(**result)
    except Exception:
        raise


@router.get("/staleness-stats")
def get_staleness_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get statistics about stale issues.

    Returns counts of issues needing verification.
    """
    from ..services import staleness_service

    return staleness_service.get_stale_issues_count(db, current_user.id)


@router.post("/verify-bulk")
def bulk_verify_issues(
    limit: int = Query(50, le=100, description="Maximum issues to verify"),
    min_age_days: int = Query(7, ge=1, description="Only verify issues not checked in N days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bulk verify issues that haven't been checked recently.

    Useful for keeping issue status up-to-date.
    """
    from ..services import staleness_service

    result = staleness_service.bulk_verify_issues(
        db=db,
        user_id=current_user.id,
        limit=limit,
        min_age_days=min_age_days,
    )

    return result


# =============================================================================
# Export Endpoints
# =============================================================================


@router.get("/export")
def export_issues(
    format: Literal["csv", "json"] = Query("csv"),
    bookmarks_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export issues to CSV or JSON format."""
    if bookmarks_only:
        issues = issue_service.get_bookmarks(db, current_user)
        # All issues are bookmarked
        bookmarked_ids = {i.id for i in issues}
    else:
        repo = IssueRepository(db)
        issues, _, bookmarked_ids = repo.list_with_bookmarks(
            user_id=current_user.id,
            filters={"is_active": True},
            offset=0,
            limit=1000,
            skip_count=True,  # Skip count for export (not needed)
        )

    # Convert to dicts using batch serialization
    issues_data = issue_service.batch_issue_to_dict(issues, bookmarked_ids)

    if format == "json":
        json_content = json.dumps(issues_data, indent=2, default=str)
        return StreamingResponse(
            io.BytesIO(json_content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=issues.json"},
        )
    else:
        output = io.StringIO()
        if issues_data:
            fieldnames = [
                "id",
                "title",
                "url",
                "difficulty",
                "issue_type",
                "repo_owner",
                "repo_name",
                "repo_stars",
                "score",
                "technologies",
                "labels",
                "created_at",
                "is_bookmarked",
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for issue in issues_data:
                row = {**issue}
                row["technologies"] = ", ".join(issue.get("technologies", []))
                row["labels"] = ", ".join(issue.get("labels", []))
                writer.writerow(row)

        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=issues.csv"},
        )


# =============================================================================
# Single Issue Endpoints
# =============================================================================


@router.get("/{issue_id}", response_model=IssueDetailResponse)
def get_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed information about an issue."""
    repo = IssueRepository(db)
    issue = repo.get_by_id(issue_id, current_user.id)

    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    is_bookmarked = (
        db.query(IssueBookmark)
        .filter(IssueBookmark.user_id == current_user.id, IssueBookmark.issue_id == issue_id)
        .first()
        is not None
    )

    return IssueDetailResponse(**issue_service.issue_to_detail_dict(issue, is_bookmarked))


@router.post("/{issue_id}/bookmark")
def bookmark_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bookmark an issue."""
    issue_service.bookmark_issue(db, current_user, issue_id)
    return {"status": "bookmarked"}


@router.delete("/{issue_id}/bookmark")
def remove_bookmark(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove bookmark from an issue."""
    issue_service.remove_bookmark(db, current_user, issue_id)
    return {"status": "removed"}


@router.post("/{issue_id}/score")
def score_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Score a specific issue against user profile."""
    try:
        from workers.tasks import score_single_issue_task

        task = score_single_issue_task.delay(current_user.id, issue_id)
        return {"task_id": task.id, "status": "scoring_queued"}
    except ImportError:
        # Synchronous fallback
        repo = IssueRepository(db)
        issue = repo.get_by_id(issue_id, current_user.id)

        if not issue:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

        profile_repo = ProfileRepository(db)
        profile = profile_repo.get_by_user_id(current_user.id)

        if not profile:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Profile required")

        scoring_service = ScoringService(repo)
        result = scoring_service.score_issue(
            issue.to_dict(),
            {
                "skills": profile.skills or [],
                "experience_level": profile.experience_level,
                "interests": profile.interests or [],
                "preferred_languages": profile.preferred_languages or [],
                "time_availability_hours_per_week": profile.time_availability_hours_per_week,
            },
        )

        repo.update_cached_scores({issue_id: result["total_score"]})

        return {"score": result["total_score"], "breakdown": result["breakdown"]}


# =============================================================================
# Issue Notes Endpoints
# =============================================================================


@router.get("/{issue_id}/notes", response_model=NotesListResponse)
def get_issue_notes(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all notes for an issue."""
    repo = IssueRepository(db)
    issue = repo.get_by_id(issue_id, current_user.id)

    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    notes = (
        db.query(IssueNote)
        .filter(IssueNote.user_id == current_user.id, IssueNote.issue_id == issue_id)
        .order_by(IssueNote.created_at.desc())
        .all()
    )
    return NotesListResponse(notes=[NoteResponse.model_validate(n) for n in notes])


@router.post("/{issue_id}/notes", response_model=NoteResponse)
def create_issue_note(
    issue_id: int,
    payload: NoteCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a note to an issue."""
    repo = IssueRepository(db)
    issue = repo.get_by_id(issue_id, current_user.id)

    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    note = IssueNote(user_id=current_user.id, issue_id=issue_id, content=payload.content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return NoteResponse.model_validate(note)


@router.delete("/{issue_id}/notes/{note_id}")
def delete_issue_note(
    issue_id: int,
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a note from an issue."""
    note = (
        db.query(IssueNote)
        .filter(
            IssueNote.id == note_id,
            IssueNote.user_id == current_user.id,
            IssueNote.issue_id == issue_id,
        )
        .one_or_none()
    )
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    db.delete(note)
    db.commit()
    return {"status": "deleted"}


# =============================================================================
# Staleness & Verification Endpoints
# =============================================================================


@router.post("/{issue_id}/verify-status")
def verify_issue_status(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verify the current status of an issue with GitHub API.

    Checks if the issue is still open or has been closed.
    """
    from ..services import staleness_service

    repo = IssueRepository(db)
    issue = repo.get_by_id(issue_id, current_user.id)

    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    result = staleness_service.verify_issue_status(db, issue)

    if not result.get("verified"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to verify issue: {result.get('error', 'Unknown error')}",
        )

    return {
        "issue_id": issue_id,
        "status": result["status"],
        "changed": result["changed"],
        "close_reason": result.get("close_reason"),
        "verified_at": issue.last_verified_at.isoformat() if issue.last_verified_at else None,
    }
