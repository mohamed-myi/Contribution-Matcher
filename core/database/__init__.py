"""
Unified Database Package.

This package provides both:
1. New DatabaseManager with connection pooling (recommended)
2. Legacy functions for backward compatibility

NEW API (recommended):
    from core.database import db, get_db, Base
    
    db.initialize()
    with db.session() as session:
        issues = session.query(Issue).all()

LEGACY API (deprecated, for backward compatibility):
    from core.database import upsert_issue, query_issues
    
    issue_id = upsert_issue(title="...", url="...")
    issues = query_issues(limit=10)
"""

# New API - DatabaseManager from the internal module
from core._database_manager import Base, DatabaseManager, db, get_db

# Legacy API - Re-export all functions from the legacy module
# These are deprecated but maintained for backward compatibility
from core.database.database import (
    DB_PATH,
    db_conn,
    export_to_csv,
    export_to_json,
    get_all_issue_urls,
    get_issue_embedding,
    get_issue_technologies,
    get_labeling_statistics,
    get_repo_metadata,
    get_statistics,
    get_variety_statistics,
    init_db,
    mark_issues_inactive,
    query_issues,
    query_unlabeled_issues,
    replace_issue_technologies,
    update_issue_label,
    upsert_issue,
    upsert_issue_embedding,
    upsert_repo_metadata,
)

__all__ = [
    # New API
    "Base",
    "DatabaseManager",
    "db",
    "get_db",
    # Legacy database functions
    "DB_PATH",
    "db_conn",
    "export_to_csv",
    "export_to_json",
    "get_all_issue_urls",
    "get_issue_embedding",
    "get_issue_technologies",
    "get_labeling_statistics",
    "get_repo_metadata",
    "get_statistics",
    "get_variety_statistics",
    "init_db",
    "mark_issues_inactive",
    "query_issues",
    "query_unlabeled_issues",
    "replace_issue_technologies",
    "update_issue_label",
    "upsert_issue",
    "upsert_issue_embedding",
    "upsert_repo_metadata",
]
