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
from core.cli.db_helpers import (
    get_labeling_statistics,
    query_issues,
    update_issue_label,
    upsert_issue,
)
from core.db import Base, DatabaseManager, db, get_db

# Re-export deprecated functions for test compatibility
# TODO: Update tests to use repository pattern instead

__all__ = [
    "Base",
    "DatabaseManager",
    "db",
    "get_db",
    # Deprecated functions for test compatibility
    "query_issues",
    "upsert_issue",
    "update_issue_label",
    "get_labeling_statistics",
]
