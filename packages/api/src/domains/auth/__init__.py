"""
Auth Domain.

Handles authentication and authorization:
- GitHub OAuth flow
- JWT token management
- User session management
"""

from .handlers import router as auth_router
from .service import AuthService

__all__ = ["auth_router", "AuthService"]
