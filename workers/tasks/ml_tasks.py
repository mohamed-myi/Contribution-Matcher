"""
ML model training tasks.

Handles training, evaluation, and maintenance of ML models.
Queue: ml (single worker, resource intensive)
"""

from typing import Dict, List, Optional

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from core.logging import get_logger

logger = get_logger("worker.ml")


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
    
    logger.info("training_started", user_id=user_id, model_type=model_type, use_hyperopt=use_hyperopt)
    
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
            logger.warning("training_no_metrics", user_id=user_id)
            return {
                "success": False,
                "user_id": user_id,
                "error": "Insufficient training data",
            }
        
        # Invalidate ML model cache to force reload
        scoring_service = ScoringService()
        scoring_service.invalidate_model_cache()
        
        logger.info("training_complete", accuracy=metrics.get('accuracy'))
        
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
        logger.error("training_failed", error=str(exc), error_type=type(exc).__name__)
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
    logger.info("evaluation_started", user_id=user_id)
    
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
        logger.error("evaluation_failed", error=str(exc))
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
    issue_ids: Optional[List[int]] = None,
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
    from core.models import Issue
    from core.scoring.feature_extractor import get_text_embeddings
    
    logger.info("embedding_generation_started", batch_size=batch_size)
    
    try:
        with db.session() as session:
            # Get issues to process
            if issue_ids:
                query = session.query(Issue).filter(Issue.id.in_(issue_ids))
            else:
                # Get active issues (embeddings are cached by get_text_embeddings)
                query = session.query(Issue).filter(Issue.is_active == True)
            
            issues = query.limit(batch_size * 10).all()
        
        processed = 0
        for issue in issues:
            try:
                # Generate embeddings (auto-cached by get_text_embeddings)
                issue_dict = {"id": issue.id, "title": issue.title, "body": issue.body}
                get_text_embeddings(issue_dict)
                processed += 1
                
            except Exception as e:
                logger.warning("embedding_failed", issue_id=issue.id, error=str(e))
        
        logger.info("embedding_generation_complete", processed=processed)
        
        return {
            "processed": processed,
            "total_requested": len(issues),
        }
        
    except Exception as exc:
        logger.error("embedding_generation_failed", error=str(exc))
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
    
    logger.info("cleanup_models_started", keep_versions=keep_versions)
    
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
                logger.debug("deleted_model", path=str(f))
            except Exception as e:
                logger.warning("delete_model_failed", path=str(f), error=str(e))
    
    logger.info("cleanup_models_complete", deleted=deleted)
    
    return {"deleted": deleted}

