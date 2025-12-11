"""
Machine learning endpoints for labeling and training.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user, validate_csrf
from ..database import get_db
from ..models import User
from ..schemas import (
    EvaluateModelRequest,
    IssueResponse,
    LabeledIssueResponse,
    LabeledIssuesResponse,
    LabelRequest,
    LabelStatusResponse,
    ModelInfoResponse,
    TrainModelRequest,
    UnlabeledIssuesResponse,
)
from ..services import issue_service, ml_service

router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/label/{issue_id}", dependencies=[Depends(validate_csrf)])
def label_issue(
    issue_id: int,
    payload: LabelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply a good/bad label to an issue for the current user."""
    ml_service.label_issue(db, current_user, issue_id, payload.label)
    return {"status": "ok"}


@router.get("/label-status", response_model=LabelStatusResponse)
def get_label_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Summarize labeling progress for training readiness."""
    stats = ml_service.label_status(db, current_user)
    return LabelStatusResponse(
        labeled_count=stats.get("total", 0),
        good_count=stats.get("good", 0),
        bad_count=stats.get("bad", 0),
        required=200,
    )


@router.get("/unlabeled-issues", response_model=UnlabeledIssuesResponse)
def get_unlabeled_issues(
    limit: int = Query(default=20, ge=1, le=100),
    include_others: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List unlabeled issues prioritized for the current user."""
    issues = ml_service.unlabeled_issues(
        db, current_user, limit=limit, include_others=include_others
    )
    issue_responses = []
    for issue in issues:
        serialized = issue_service.issue_to_dict(issue)
        issue_responses.append(IssueResponse(**serialized))
    return UnlabeledIssuesResponse(issues=issue_responses)


@router.get("/labeled-issues", response_model=LabeledIssuesResponse)
def get_labeled_issues(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    label_filter: str = Query(
        default=None, description="Filter by label: good, bad, or null for all"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get labeled issues for the current user with pagination and filtering."""
    results, total, good_count, bad_count = ml_service.labeled_issues(
        db, current_user, limit=limit, offset=offset, label_filter=label_filter
    )

    issue_responses = []
    for issue, label in results:
        # Get technologies for the issue
        techs = [t.technology for t in issue.technologies] if issue.technologies else []

        issue_responses.append(
            LabeledIssueResponse(
                id=issue.id,
                title=issue.title,
                url=issue.url,
                difficulty=issue.difficulty,
                issue_type=issue.issue_type,
                repo_owner=issue.repo_owner,
                repo_name=issue.repo_name,
                repo_stars=issue.repo_stars,
                description=(
                    issue.body[:200] + "..." if issue.body and len(issue.body) > 200 else issue.body
                ),
                technologies=techs,
                label=label.label,
                labeled_at=label.labeled_at,
            )
        )

    return LabeledIssuesResponse(
        issues=issue_responses,
        total=total,
        good_count=good_count,
        bad_count=bad_count,
    )


@router.delete("/label/{issue_id}", dependencies=[Depends(validate_csrf)])
def remove_issue_label(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a label from an issue."""
    ml_service.remove_label(db, current_user, issue_id)
    return {"status": "ok"}


@router.post("/train", response_model=ModelInfoResponse, dependencies=[Depends(validate_csrf)])
def train_model(
    payload: TrainModelRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload is None:
        payload = TrainModelRequest()
    result = ml_service.train_model(db, current_user, payload)
    return result


@router.post("/evaluate", dependencies=[Depends(validate_csrf)])
def evaluate_model(
    payload: EvaluateModelRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload is None:
        payload = EvaluateModelRequest()
    return ml_service.evaluate_model(db, current_user, payload)


@router.get("/model-info", response_model=ModelInfoResponse)
def get_model_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    info = ml_service.model_info(db, current_user)
    if info is None:
        return ModelInfoResponse(
            trained_at=None,
            model_type="none",
            metrics=None,
            model_path=None,
            training_samples=0,
        )
    return info
