"""
Issues Domain.

Handles issue management:
- Issue CRUD operations
- Bookmarks
- Discovery
- Staleness checking
"""

from .handlers import router as issues_router
from .service import IssueService

__all__ = ["issues_router", "IssueService"]
