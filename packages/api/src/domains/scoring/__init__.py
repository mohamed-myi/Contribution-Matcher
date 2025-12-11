"""
Scoring Domain.

Handles issue scoring and matching:
- Score calculation
- Top matches
- Score caching
"""

from .handlers import router as scoring_router
from .service import ScoringService

__all__ = ["scoring_router", "ScoringService"]
