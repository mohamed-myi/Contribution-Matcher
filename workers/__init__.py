"""
Celery Background Workers.

Provides background tasks for issue discovery, score computation, and ML training.

Usage:
    celery -A workers worker --loglevel=info
    celery -A workers worker -Q discovery --loglevel=info
    celery -A workers beat --loglevel=info
"""

from workers.celery_app import celery_app

__all__ = ["celery_app"]
