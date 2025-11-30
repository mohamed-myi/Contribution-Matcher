"""
Machine learning endpoints for labeling and training.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import (
    EvaluateModelRequest,
    LabelRequest,
    LabelStatusResponse,
    ModelInfoResponse,
    TrainModelRequest,
    UnlabeledIssuesResponse,
    IssueResponse,
)
from ..services import issue_service, ml_service

router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/label/{issue_id}")
def label_issue(
    issue_id: int,
    payload: LabelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ml_service.label_issue(db, current_user, issue_id, payload.label)
    return {"status": "ok"}


@router.get("/label-status", response_model=LabelStatusResponse)
def get_label_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issues = ml_service.unlabeled_issues(db, current_user, limit=limit)
    issue_responses = []
    for issue in issues:
        serialized = issue_service.serialize_issue(issue)
        issue_responses.append(IssueResponse(**serialized))
    return UnlabeledIssuesResponse(issues=issue_responses)


@router.post("/train", response_model=ModelInfoResponse)
def train_model(
    payload: TrainModelRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload is None:
        payload = TrainModelRequest()
    result = ml_service.train_model(db, current_user, payload)
    return result


@router.post("/evaluate")
def evaluate_model(
    payload: EvaluateModelRequest = None,
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
