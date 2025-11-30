"""
Issue discovery and management endpoints.

Refactored to use:
- Core repositories for database access
- Celery tasks for async discovery
- Redis caching for performance
"""

import csv
import io
import json
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.db import db as core_db
from core.repositories import IssueRepository, ProfileRepository
from core.services import ScoringService
from core.cache import cache, CacheKeys

from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models import User, IssueLabel, IssueNote, Issue
from ..schemas import (
    IssueDetailResponse,
    IssueDiscoverRequest,
    IssueFilterParams,
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
# Discovery Endpoints
# =============================================================================

@router.post("/discover", response_model=IssueListResponse)
def discover_issues(
    request: IssueDiscoverRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Synchronous issue discovery.
    
    For large discoveries, use POST /discover/async instead.
    """
    issues = issue_service.discover_issues_for_user(db, current_user, request)
    return IssueListResponse(
        issues=[IssueResponse(**issue_service.issue_to_response_dict(i, current_user.id, db)) for i in issues],
        total=len(issues),
    )


@router.post("/discover/async")
def discover_issues_async(
    request: IssueDiscoverRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Asynchronous issue discovery using Celery.
    
    Returns a task_id that can be used to check status.
    Recommended for discovering large numbers of issues.
    """
    try:
        from workers.tasks import discover_issues_task
        
        # Queue the discovery task
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
            detail="Celery workers not available. Use synchronous discovery instead.",
        )


@router.get("/discover/task/{task_id}")
def get_discovery_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Check status of an async discovery task.
    """
    try:
        from workers.celery_app import celery_app
        
        result = celery_app.AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "status": result.status,
        }
        
        if result.ready():
            if result.successful():
                response["result"] = result.result
            else:
                response["error"] = str(result.result)
        
        return response
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Celery not available",
        )


# =============================================================================
# List & Query Endpoints
# =============================================================================

@router.get("", response_model=IssueListResponse)
def list_issues(
    difficulty: str = Query(None),
    technology: str = Query(None),
    language: str = Query(None),
    repo_owner: str = Query(None),
    issue_type: str = Query(None),
    days_back: int = Query(30),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    order_by: str = Query("created_at", description="Order by: created_at or score"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List issues with filtering and pagination.
    
    Uses repository pattern with efficient bookmark loading.
    """
    # Build filters
    filters = {
        "difficulty": difficulty,
        "technology": technology,
        "language": language,
        "repo_owner": repo_owner,
        "issue_type": issue_type,
        "days_back": days_back,
        "order_by": order_by,
        "is_active": True,
    }
    
    # Use repository with batch bookmark loading
    repo = IssueRepository(db)
    issues, total, bookmarked_ids = repo.list_with_bookmarks(
        user_id=current_user.id,
        filters=filters,
        offset=offset,
        limit=limit,
    )
    
    # Build response with bookmark status pre-loaded
    issue_responses = []
    for issue in issues:
        response_dict = _issue_to_response(issue)
        response_dict["is_bookmarked"] = issue.id in bookmarked_ids
        issue_responses.append(IssueResponse(**response_dict))
    
    return IssueListResponse(issues=issue_responses, total=total)


@router.get("/bookmarks", response_model=IssueListResponse)
def get_bookmarks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all bookmarked issues."""
    issues = issue_service.get_bookmarks(db, current_user)
    return IssueListResponse(
        issues=[IssueResponse(**issue_service.issue_to_response_dict(i, current_user.id, db)) for i in issues],
        total=len(issues),
    )


@router.get("/top-matches")
def get_top_matches(
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get top matching issues based on cached scores.
    
    Uses ScoringService with Redis caching.
    """
    # Get profile
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
    
    # Use cached scoring service
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
    """Get issue statistics."""
    repo = IssueRepository(db)
    stats = repo.get_variety_stats(current_user.id)
    
    # Get labeled count
    labeled_count = db.query(IssueLabel).filter(
        IssueLabel.user_id == current_user.id
    ).count()
    
    # Get bookmark count
    from ..models import IssueBookmark
    bookmark_count = db.query(IssueBookmark).filter(
        IssueBookmark.user_id == current_user.id
    ).count()
    
    return IssueStatsResponse(
        total=stats.get("total", 0),
        bookmarked=bookmark_count,
        labeled=labeled_count,
        top_score=None,
        by_difficulty=stats.get("by_difficulty", {}),
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
    """Get detailed information about a specific issue."""
    repo = IssueRepository(db)
    issue = repo.get_by_id(issue_id, current_user.id)
    
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    
    response = issue_service.issue_to_response_dict(issue, current_user.id, db)
    response["body"] = issue.body
    response["description"] = issue.body[:500] if issue.body else None
    response["repo_url"] = issue.repo_url
    response["repo_forks"] = issue.repo_forks
    response["time_estimate"] = issue.time_estimate
    response["contributor_count"] = issue.contributor_count
    response["is_active"] = issue.is_active if issue.is_active is not None else True
    
    return IssueDetailResponse(**response)


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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger scoring for a specific issue.
    
    Scores are computed in background and cached.
    """
    try:
        from workers.tasks import score_single_issue_task
        
        # Queue background scoring
        task = score_single_issue_task.delay(current_user.id, issue_id)
        
        return {
            "task_id": task.id,
            "status": "scoring_queued",
        }
    except ImportError:
        # Fall back to synchronous scoring
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
        
        # Update cached score
        repo.update_cached_scores({issue_id: result["total_score"]})
        
        return {"score": result["total_score"], "breakdown": result["breakdown"]}


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
    else:
        filters = IssueFilterParams(limit=1000, offset=0)
        issues = issue_service.list_issues(db, current_user, filters)
    
    # Convert to serializable format
    issues_data = [
        issue_service.issue_to_response_dict(issue, current_user.id, db)
        for issue in issues
    ]
    
    if format == "json":
        json_content = json.dumps(issues_data, indent=2, default=str)
        return StreamingResponse(
            io.BytesIO(json_content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=issues.json"}
        )
    else:
        output = io.StringIO()
        if issues_data:
            fieldnames = ["id", "title", "url", "difficulty", "issue_type", 
                         "repo_owner", "repo_name", "repo_stars", "score", 
                         "technologies", "labels", "created_at", "is_bookmarked"]
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
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
            headers={"Content-Disposition": "attachment; filename=issues.csv"}
        )


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
    
    note = IssueNote(
        user_id=current_user.id,
        issue_id=issue_id,
        content=payload.content,
    )
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
# Helper Functions
# =============================================================================

def _issue_to_response(issue: Issue) -> dict:
    """Convert Issue model to response dict (without DB queries)."""
    issue_number = None
    if issue.url:
        try:
            issue_number = int(issue.url.rstrip('/').split('/')[-1])
        except (ValueError, IndexError):
            pass
    
    description = None
    if issue.body:
        description = issue.body[:300] + ('...' if len(issue.body) > 300 else '')
    
    return {
        "id": issue.id,
        "title": issue.title,
        "url": issue.url,
        "difficulty": issue.difficulty,
        "issue_type": issue.issue_type,
        "repo_owner": issue.repo_owner,
        "repo_name": issue.repo_name,
        "repo_stars": issue.repo_stars,
        "issue_number": issue_number,
        "description": description,
        "technologies": [tech.technology for tech in issue.technologies] if issue.technologies else [],
        "labels": issue.labels or [],
        "repo_topics": issue.repo_topics or [],
        "created_at": issue.created_at,
        "score": issue.cached_score,
    }
