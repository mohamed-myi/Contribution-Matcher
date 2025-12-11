"""
Database Package.

New API (recommended):
    from core.database import db, get_db, Base
    db.initialize()
    with db.session() as session:
        issues = session.query(Issue).all()

For data operations, use the repository pattern:
    from core.repositories import IssueRepository
    repo = IssueRepository(session)
    issues = repo.list_with_bookmarks(user_id, filters)
"""

# New API - from the consolidated db module
from core.db import Base, DatabaseManager, db, get_db

__all__ = [
    "Base",
    "DatabaseManager",
    "db",
    "get_db",
]
