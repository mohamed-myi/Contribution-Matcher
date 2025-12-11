"""
Machine learning service for labeling issues and training per-user models.
"""

from __future__ import annotations

from typing import Any

import joblib
import numpy as np
from fastapi import HTTPException, status
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import exists
from sqlalchemy.orm import Session

from ..models import Issue, IssueLabel, User, UserMLModel
from ..schemas import EvaluateModelRequest, ModelInfoResponse, TrainModelRequest
from . import issue_service
from .feature_cache_service import get_breakdown_and_features, get_model_dir


def label_issue(db: Session, user: User, issue_id: int, label: str) -> None:
    """Assign or update a label ('good'|'bad') for an issue."""
    issue = issue_service.get_issue(db, user, issue_id)
    label = label.lower()
    if label not in ("good", "bad"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid label; must be 'good' or 'bad'.",
        )
    existing = (
        db.query(IssueLabel)
        .filter(IssueLabel.user_id == user.id, IssueLabel.issue_id == issue.id)
        .one_or_none()
    )
    if existing:
        existing.label = label
    else:
        db.add(IssueLabel(user_id=user.id, issue_id=issue.id, label=label))
    db.commit()


def label_status(db: Session, user: User) -> dict[str, int]:
    """Return aggregate counts of labeled, good, bad, and remaining issues."""
    total = db.query(IssueLabel).filter(IssueLabel.user_id == user.id).count()
    good = (
        db.query(IssueLabel)
        .filter(IssueLabel.user_id == user.id, IssueLabel.label == "good")
        .count()
    )
    bad = (
        db.query(IssueLabel)
        .filter(IssueLabel.user_id == user.id, IssueLabel.label == "bad")
        .count()
    )
    remaining = (
        db.query(Issue)
        .filter(Issue.user_id == user.id)
        .filter(
            ~exists().where((IssueLabel.issue_id == Issue.id) & (IssueLabel.user_id == user.id))
        )
        .count()
    )
    return {"total": total, "good": good, "bad": bad, "remaining": remaining}


def unlabeled_issues(
    db: Session, user: User, limit: int = 20, include_others: bool = False
) -> list[Issue]:
    """
    Get unlabeled issues for the user to label.

    Args:
        db: Database session
        user: Current user
        limit: Maximum number of issues to return
        include_others: If True, include issues discovered by other users
    """
    subquery = db.query(IssueLabel.issue_id).filter(IssueLabel.user_id == user.id).subquery()

    query = db.query(Issue).filter(
        ~Issue.id.in_(subquery),  # type: ignore[arg-type]
        Issue.is_active,
    )

    # Filter by user_id unless include_others is True
    if not include_others:
        query = query.filter(Issue.user_id == user.id)

    return query.order_by(Issue.created_at.desc()).limit(limit).all()


def labeled_issues(
    db: Session,
    user: User,
    limit: int = 50,
    offset: int = 0,
    label_filter: str | None = None,
) -> tuple[list[tuple[Issue, IssueLabel]], int, int, int]:
    """
    Get labeled issues for the user with their labels.

    Args:
        db: Database session
        user: Current user
        limit: Maximum number of issues to return
        offset: Offset for pagination
        label_filter: Filter by label ("good", "bad", or None for all)

    Returns:
        Tuple of (list of (Issue, IssueLabel) pairs, total count, good count, bad count)
    """
    base_query = (
        db.query(Issue, IssueLabel)
        .join(IssueLabel, IssueLabel.issue_id == Issue.id)
        .filter(
            IssueLabel.user_id == user.id,
            Issue.is_active,
        )
    )

    # Get counts
    good_count = (
        db.query(IssueLabel)
        .filter(IssueLabel.user_id == user.id, IssueLabel.label == "good")
        .count()
    )
    bad_count = (
        db.query(IssueLabel)
        .filter(IssueLabel.user_id == user.id, IssueLabel.label == "bad")
        .count()
    )
    total_count = good_count + bad_count

    # Apply label filter
    if label_filter:
        base_query = base_query.filter(IssueLabel.label == label_filter.lower())

    # Get paginated results
    results = base_query.order_by(IssueLabel.labeled_at.desc()).offset(offset).limit(limit).all()

    # Convert Row objects to tuples
    results_tuples = [(row[0], row[1]) for row in results] if results else []

    return results_tuples, total_count, good_count, bad_count


def remove_label(db: Session, user: User, issue_id: int) -> None:
    """
    Remove a label from an issue.

    Args:
        db: Database session
        user: Current user
        issue_id: Issue ID to remove label from
    """
    existing = (
        db.query(IssueLabel)
        .filter(IssueLabel.user_id == user.id, IssueLabel.issue_id == issue_id)
        .one_or_none()
    )
    if existing:
        db.delete(existing)
        db.commit()


def _build_training_dataset(db: Session, user: User) -> tuple[np.ndarray, np.ndarray]:
    """Assemble feature matrix and labels from the user's labeled issues."""
    labeled = (
        db.query(Issue, IssueLabel)
        .join(IssueLabel, IssueLabel.issue_id == Issue.id)
        .filter(Issue.user_id == user.id, IssueLabel.user_id == user.id)
        .all()
    )
    if not labeled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No labeled issues found."
        )

    X: list[list[float]] = []
    y: list[int] = []
    for issue, label in labeled:
        _, features = get_breakdown_and_features(db, user, issue)
        X.append(features)
        y.append(1 if label.label == "good" else 0)

    good = sum(y)
    bad = len(y) - good
    if good == 0 or bad == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Need at least one 'good' and one 'bad' label to train.",
        )

    return np.array(X), np.array(y)


def _split_dataset(X: np.ndarray, y: np.ndarray, test_size: float) -> tuple[np.ndarray, ...]:
    """Split dataset with safeguards for small sample sizes."""
    min_test_size = max(0.2, 2 / len(y))
    test_size = max(test_size, min_test_size)
    if test_size >= 1.0:
        test_size = 0.5
    if len(y) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Need at least 4 labeled issues to train.",
        )
    return train_test_split(X, y, test_size=test_size, random_state=42, stratify=y)


def _train_pipeline(
    model_type: str, X_train, y_train, X_test, y_test
) -> tuple[Any, dict[str, Any]]:  # type: ignore[no-untyped-def]
    """Train a model pipeline (logistic or XGBoost) and return metrics."""
    if model_type == "xgboost":
        try:
            import xgboost as xgb
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="xgboost not installed. Install it to use xgboost model_type.",
            ) from exc
        model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=42,
            use_label_encoder=False,
        )
        pipeline = model
        pipeline.fit(X_train, y_train)
        y_pred = pipeline.predict(X_test)
    else:
        pipeline = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000),
        )
        pipeline.fit(X_train, y_train)
        y_pred = pipeline.predict(X_test)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "samples": int(len(y_train) + len(y_test)),
    }
    return pipeline, metrics


def evaluate_model(
    db: Session,
    user: User,
    payload: EvaluateModelRequest,
) -> dict:
    """Evaluate a model without persisting artifacts."""
    X, y = _build_training_dataset(db, user)
    X_train, X_test, y_train, y_test = _split_dataset(X, y, payload.test_size)
    _, metrics = _train_pipeline(payload.model_type, X_train, y_train, X_test, y_test)
    metrics["model_type"] = payload.model_type
    return metrics


def train_model(
    db: Session,
    user: User,
    payload: TrainModelRequest,
) -> ModelInfoResponse:
    """Train and persist a per-user model; returns saved model metadata."""
    X, y = _build_training_dataset(db, user)
    X_train, X_test, y_train, y_test = _split_dataset(X, y, payload.test_size)
    pipeline, metrics = _train_pipeline(payload.model_type, X_train, y_train, X_test, y_test)

    user_dir = get_model_dir() / f"user_{user.id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    model_filename = f"issue_classifier_{payload.model_type}.pkl"
    model_path = user_dir / model_filename
    joblib.dump(pipeline, model_path)

    record = (
        db.query(UserMLModel)
        .filter(UserMLModel.user_id == user.id, UserMLModel.model_type == payload.model_type)
        .one_or_none()
    )
    if record:
        record.model_path = str(model_path)
        record.metrics = metrics
        record.description = payload.description
    else:
        record = UserMLModel(
            user_id=user.id,
            model_type=payload.model_type,
            model_path=str(model_path),
            metrics=metrics,
            description=payload.description,
        )
        db.add(record)
    db.commit()
    db.refresh(record)

    return ModelInfoResponse(
        trained_at=record.trained_at,
        model_type=record.model_type,
        metrics=record.metrics,
        model_path=record.model_path,
        training_samples=metrics.get("samples"),
    )


def model_info(db: Session, user: User) -> ModelInfoResponse | None:
    record = (
        db.query(UserMLModel)
        .filter(UserMLModel.user_id == user.id)
        .order_by(UserMLModel.trained_at.desc())
        .first()
    )
    if not record:
        return None
    return ModelInfoResponse(
        trained_at=record.trained_at,
        model_type=record.model_type,
        metrics=record.metrics,
        model_path=record.model_path,
        training_samples=record.metrics.get("samples") if record.metrics else None,
    )
