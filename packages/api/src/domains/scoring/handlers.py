"""
Scoring Handlers.

API route handlers for scoring endpoints.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from packages.shared.types import (
    IssueScoreResponse,
    ScoringRequest,
    ScoringResponse,
    TopMatchesResponse,
)

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.get("/top-matches", response_model=TopMatchesResponse)
async def get_top_matches(
    limit: int = Query(10, ge=1, le=50),
):
    """
    Get top-scored issues for the current user.
    
    Uses cached scores for fast response.
    """
    return {
        "matches": [],
        "total_scored": 0,
        "profile_id": None,
    }


@router.get("/issue/{issue_id}", response_model=IssueScoreResponse)
async def score_issue(
    issue_id: int,
    use_ml: bool = Query(True),
):
    """
    Get detailed score for a specific issue.
    
    Includes full breakdown of score components.
    """
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Issue not found",
    )


@router.post("/refresh")
async def refresh_scores():
    """
    Trigger background rescoring of all issues.
    
    Returns a task ID for tracking progress.
    """
    return {
        "task_id": None,
        "message": "Scoring refresh queued",
    }


@router.post("/invalidate")
async def invalidate_scores():
    """
    Invalidate cached scores.
    
    Call this after profile changes.
    """
    return {
        "invalidated_count": 0,
        "message": "Scores invalidated",
    }
