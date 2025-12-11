"""
Queue Infrastructure.

Provides Celery-based task queue integration for:
- Issue discovery
- Score calculation
- ML training
"""

from typing import Optional


def get_task_status(task_id: str) -> dict:
    """
    Get status of a Celery task.
    
    Args:
        task_id: The task ID to check.
    
    Returns:
        Dict with task status and result.
    """
    try:
        from workers.celery_app import celery_app
        result = celery_app.AsyncResult(task_id)
        
        status_info = {
            "task_id": task_id,
            "status": result.status,
            "ready": result.ready(),
        }
        
        if result.ready():
            if result.successful():
                status_info["result"] = result.result
            else:
                status_info["error"] = str(result.result)
        
        return status_info
    except ImportError:
        return {
            "task_id": task_id,
            "status": "UNKNOWN",
            "error": "Celery not available",
        }


def queue_task(task_name: str, **kwargs) -> Optional[str]:
    """
    Queue a Celery task by name.
    
    Args:
        task_name: Name of the task to queue.
        **kwargs: Arguments to pass to the task.
    
    Returns:
        Task ID or None if Celery not available.
    """
    try:
        from workers.celery_app import celery_app
        task = celery_app.send_task(task_name, kwargs=kwargs)
        return task.id
    except ImportError:
        return None


__all__ = ["get_task_status", "queue_task"]
