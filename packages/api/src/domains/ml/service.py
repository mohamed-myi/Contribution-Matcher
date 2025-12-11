"""
ML Service.

Business logic for ML operations.
"""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from core.models import Issue, IssueLabel, UserMLModel


class MLService:
    """Service for ML-related business logic."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def label_issue(
        self,
        user_id: int,
        issue_id: int,
        label: str,
    ) -> IssueLabel:
        """
        Label an issue for ML training.
        
        Args:
            user_id: User ID
            issue_id: Issue ID
            label: Label ('good' or 'bad')
        
        Returns:
            Created or updated IssueLabel
        """
        if label not in ['good', 'bad']:
            raise ValueError("Label must be 'good' or 'bad'")
        
        existing = self.session.query(IssueLabel).filter(
            IssueLabel.user_id == user_id,
            IssueLabel.issue_id == issue_id,
        ).first()
        
        if existing:
            existing.label = label
            existing.labeled_at = datetime.utcnow()
        else:
            existing = IssueLabel(
                user_id=user_id,
                issue_id=issue_id,
                label=label,
            )
            self.session.add(existing)
        
        # Also update the issue's label field
        issue = self.session.query(Issue).filter(Issue.id == issue_id).first()
        if issue:
            issue.label = label
            issue.labeled_at = datetime.utcnow()
        
        self.session.flush()
        return existing
    
    def get_labeling_stats(self, user_id: int) -> Dict:
        """Get labeling statistics for a user."""
        from sqlalchemy import func
        
        by_label = dict(
            self.session.query(IssueLabel.label, func.count(IssueLabel.id))
            .filter(IssueLabel.user_id == user_id)
            .group_by(IssueLabel.label)
            .all()
        )
        
        total = sum(by_label.values()) if by_label else 0
        good_count = by_label.get('good', 0)
        bad_count = by_label.get('bad', 0)
        
        # Check if ready for training (minimum 200 labeled)
        ready_for_training = total >= 200 and good_count > 0 and bad_count > 0
        
        return {
            "total_labeled": total,
            "good_count": good_count,
            "bad_count": bad_count,
            "balance_ratio": min(good_count, bad_count) / max(good_count, bad_count, 1),
            "ready_for_training": ready_for_training,
            "labels_needed": max(0, 200 - total),
        }
    
    def get_unlabeled_issues(
        self,
        user_id: int,
        limit: int = 50,
    ) -> List[Issue]:
        """Get unlabeled issues for the user to label."""
        # Get already labeled issue IDs
        labeled_ids = [
            row[0] for row in
            self.session.query(IssueLabel.issue_id)
            .filter(IssueLabel.user_id == user_id)
            .all()
        ]
        
        # Get unlabeled active issues
        query = self.session.query(Issue).filter(
            Issue.user_id == user_id,
            Issue.is_active == True,
        )
        
        if labeled_ids:
            query = query.filter(Issue.id.notin_(labeled_ids))
        
        return query.order_by(Issue.created_at.desc()).limit(limit).all()
    
    def get_model_info(self, user_id: int) -> Optional[Dict]:
        """Get information about the user's trained model."""
        model = self.session.query(UserMLModel).filter(
            UserMLModel.user_id == user_id,
            UserMLModel.is_active == True,
        ).order_by(UserMLModel.created_at.desc()).first()
        
        if not model:
            return None
        
        return {
            "model_type": model.model_type,
            "version": model.version,
            "trained_at": model.created_at.isoformat() if model.created_at else None,
            "metrics": model.metrics or {},
            "sample_count": model.training_sample_count or 0,
        }
    
    def queue_training(self, user_id: int) -> str:
        """
        Queue model training task.
        
        Returns:
            Task ID
        """
        try:
            from workers.tasks import train_model_task
            task = train_model_task.delay(user_id=user_id)
            return task.id
        except ImportError:
            raise RuntimeError("Celery workers not available")
