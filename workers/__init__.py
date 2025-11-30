"""
Celery Background Workers.

This package provides background task processing for:
- Issue discovery (rate-limited GitHub API calls)
- Score computation (parallelized)
- ML model training (resource-intensive)

Usage:
    # Start worker for all queues
    celery -A workers worker --loglevel=info
    
    # Start worker for specific queue
    celery -A workers worker -Q discovery --loglevel=info
    
    # Start beat scheduler
    celery -A workers beat --loglevel=info
"""

from workers.celery_app import celery_app

__all__ = ["celery_app"]

