"""
Scoring endpoints for issue matchmaking.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import ScoreBreakdownResponse, TopMatchesResponse, IssueResponse
from ..services import scoring_service

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.post("/score-all")
def score_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Score all issues for the current user and persist results."""
    results = scoring_service.score_all_issues(db, current_user)
    return {"scored": len(results), "issues": results}


@router.get("/top-matches", response_model=TopMatchesResponse)
def top_matches(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return top-matching issues for the current user."""
    issues = scoring_service.get_top_matches(db, current_user, limit=limit)
    return TopMatchesResponse(issues=issues)


@router.get("/{issue_id}", response_model=ScoreBreakdownResponse)
def score_single_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return detailed score breakdown for a single issue."""
    return scoring_service.get_score_for_issue(db, current_user, issue_id)
