"""
Profiles Domain.

Handles user profile management:
- Profile CRUD operations
- Profile import from GitHub/Resume
"""

from .handlers import router as profiles_router
from .service import ProfileService

__all__ = ["profiles_router", "ProfileService"]
