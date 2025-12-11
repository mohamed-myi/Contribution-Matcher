"""
ML Handlers.

API route handlers for ML endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from packages.shared.types import (
    LabelIssueRequest,
    ModelInfoResponse,
    TrainingStatusResponse,
)
from packages.shared.enums import IssueLabel

router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/label")
async def label_issue(request: LabelIssueRequest):
    """
    Label an issue for ML training.
    
    Labels are used to train personalized recommendation models.
    """
    return {
        "issue_id": request.issue_id,
        "label": request.label,
        "message": "Issue labeled successfully",
    }


@router.get("/labeling-status")
async def get_labeling_status():
    """
    Get labeling progress and statistics.
    """
    return {
        "total_labeled": 0,
        "good_count": 0,
        "bad_count": 0,
        "balance_ratio": 0,
        "ready_for_training": False,
        "labels_needed": 200,
    }


@router.get("/unlabeled")
async def get_unlabeled_issues(
    limit: int = Query(50, ge=1, le=100),
):
    """
    Get unlabeled issues for labeling.
    """
    return {
        "items": [],
        "total": 0,
    }


@router.post("/train")
async def train_model():
    """
    Start model training.
    
    Returns a task ID for tracking progress.
    """
    return {
        "task_id": None,
        "status": "queued",
        "message": "Training not available - insufficient labeled data",
    }


@router.get("/training-status", response_model=TrainingStatusResponse)
async def get_training_status(task_id: str = Query(...)):
    """
    Get status of a training task.
    """
    return {
        "task_id": task_id,
        "status": "unknown",
        "progress": None,
        "metrics": None,
        "error": "Task not found",
    }


@router.get("/model-info", response_model=ModelInfoResponse)
async def get_model_info():
    """
    Get information about the trained model.
    """
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No trained model found",
    )
