"""
ML Domain.

Handles machine learning operations:
- Issue labeling for training
- Model training status
- Model information
"""

from .handlers import router as ml_router
from .service import MLService

__all__ = ["ml_router", "MLService"]
