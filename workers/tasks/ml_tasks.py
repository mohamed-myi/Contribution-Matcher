"""
ML model training tasks.

These tasks handle:
- Training user-specific ML models
- Model evaluation and metrics
- Model deployment (cache update)

Queue: ml (single worker, resource intensive)
"""

import logging
import os
from typing import Dict, Optional

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="workers.tasks.ml_tasks.train_model",
    max_retries=2,
    default_retry_delay=120,  # 2 minutes
    soft_time_limit=1800,  # 30 minutes
    time_limit=3600,  # 1 hour
)
def train_model_task(
    self,
    user_id: Optional[int] = None,
    model_type: str = "xgboost",
    use_hyperopt: bool = False,
) -> Dict:
    """
    Train an ML model for issue quality prediction.
    
    If user_id is provided, trains a personalized model.
    If user_id is None, trains a global model using all labeled data.
    
    Args:
        user_id: Optional user ID for personalized model
        model_type: Model type ("xgboost", "gradient_boosting", "logistic")
        use_hyperopt: Whether to use hyperparameter optimization
        
    Returns:
        Dictionary with training results and metrics
    """
    from core.services import ScoringService
    from core.cache import cache, CacheKeys
    
    logger.info(f"Starting ML model training (user_id={user_id}, type={model_type})")
    
    try:
        # Import training function
        from core.scoring.ml_trainer import train_model, train_model_v2
        
        # Choose training function based on model type
        if model_type == "xgboost":
            metrics = train_model_v2(
                use_hyperopt=use_hyperopt,
                use_advanced_features=True,
            )
        else:
            metrics = train_model()
        
        if metrics is None:
            logger.warning("Training returned no metrics (insufficient data?)")
            return {
                "success": False,
                "user_id": user_id,
                "error": "Insufficient training data",
            }
        
        # Invalidate ML model cache to force reload
        scoring_service = ScoringService()
        scoring_service.invalidate_model_cache()
        
        logger.info(f"Model training completed. Accuracy: {metrics.get('accuracy', 'N/A')}")
        
        # Schedule score recomputation for affected users
        if user_id:
            from workers.tasks.scoring_tasks import score_user_issues_task
            score_user_issues_task.delay(user_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "model_type": model_type,
            "metrics": metrics,
        }
        
    except Exception as exc:
        logger.error(f"Model training failed: {exc}")
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {
                "success": False,
                "user_id": user_id,
                "error": str(exc),
            }


@shared_task(
    bind=True,
    name="workers.tasks.ml_tasks.evaluate_model",
    max_retries=1,
    soft_time_limit=300,
    time_limit=600,
)
def evaluate_model_task(
    self,
    user_id: Optional[int] = None,
) -> Dict:
    """
    Evaluate current ML model performance.
    
    Runs cross-validation and returns detailed metrics.
    
    Args:
        user_id: Optional user ID to evaluate personalized model
        
    Returns:
        Dictionary with evaluation metrics
    """
    logger.info(f"Evaluating ML model (user_id={user_id})")
    
    try:
        from core.scoring.ml_trainer import evaluate_model_performance
        
        metrics = evaluate_model_performance()
        
        if metrics is None:
            return {
                "success": False,
                "error": "Evaluation failed or insufficient data",
            }
        
        return {
            "success": True,
            "user_id": user_id,
            "metrics": metrics,
        }
        
    except Exception as exc:
        logger.error(f"Model evaluation failed: {exc}")
        return {
            "success": False,
            "error": str(exc),
        }


@shared_task(
    name="workers.tasks.ml_tasks.generate_embeddings",
    soft_time_limit=600,
    time_limit=900,
)
def generate_embeddings_task(
    issue_ids: Optional[list] = None,
    batch_size: int = 50,
) -> Dict:
    """
    Generate BERT embeddings for issues.
    
    Embeddings are used for semantic similarity matching.
    
    Args:
        issue_ids: Optional list of issue IDs. If None, processes all without embeddings.
        batch_size: Number of issues to process per batch
        
    Returns:
        Dictionary with results
    """
    from core.db import db
    from core.models import Issue, IssueEmbedding
    from core.scoring.feature_extractor import compute_bert_embedding
    from core.database import upsert_issue_embedding
    
    logger.info("Starting embedding generation")
    
    try:
        with db.session() as session:
            # Get issues without embeddings
            if issue_ids:
                query = session.query(Issue).filter(Issue.id.in_(issue_ids))
            else:
                # Get issues without embeddings
                subquery = session.query(IssueEmbedding.issue_id)
                query = session.query(Issue).filter(
                    ~Issue.id.in_(subquery),
                    Issue.is_active == True,
                )
            
            issues = query.limit(batch_size * 10).all()  # Process up to 500
        
        processed = 0
        for issue in issues:
            try:
                # Compute embeddings
                text = f"{issue.title or ''} {issue.body or ''}"
                title_embedding, desc_embedding = compute_bert_embedding(text)
                
                # Store embeddings
                upsert_issue_embedding(
                    issue_id=issue.id,
                    description_embedding=desc_embedding,
                    title_embedding=title_embedding,
                )
                processed += 1
                
            except Exception as e:
                logger.warning(f"Embedding failed for issue {issue.id}: {e}")
        
        logger.info(f"Generated embeddings for {processed} issues")
        
        return {
            "processed": processed,
            "total_requested": len(issues),
        }
        
    except Exception as exc:
        logger.error(f"Embedding generation failed: {exc}")
        return {"error": str(exc)}


@shared_task(
    name="workers.tasks.ml_tasks.cleanup_old_models",
)
def cleanup_old_models_task(keep_versions: int = 3) -> Dict:
    """
    Clean up old model versions to save disk space.
    
    Keeps the N most recent versions of each model type.
    
    Args:
        keep_versions: Number of versions to keep
        
    Returns:
        Dictionary with cleanup results
    """
    import glob
    from pathlib import Path
    
    logger.info(f"Cleaning up old models, keeping {keep_versions} versions")
    
    models_dir = Path("models")
    if not models_dir.exists():
        return {"deleted": 0}
    
    deleted = 0
    
    # Find model files by pattern
    patterns = [
        "xgboost_model_*.pkl",
        "gradient_boosting_model_*.pkl",
        "scaler_*.pkl",
        "feature_selector_*.pkl",
    ]
    
    for pattern in patterns:
        files = sorted(
            models_dir.glob(pattern),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )
        
        # Delete old versions
        for f in files[keep_versions:]:
            try:
                f.unlink()
                deleted += 1
                logger.debug(f"Deleted old model: {f}")
            except Exception as e:
                logger.warning(f"Failed to delete {f}: {e}")
    
    logger.info(f"Deleted {deleted} old model files")
    
    return {"deleted": deleted}

