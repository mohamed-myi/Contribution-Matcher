"""
Database module.

This is the main database module providing the DatabaseManager singleton.

Usage:
    from core.db import db, get_db, Base, DatabaseManager
    # or
    from core.database import db, get_db, Base, DatabaseManager
"""

from core._database_manager import db, get_db, Base, DatabaseManager

__all__ = ["db", "get_db", "Base", "DatabaseManager"]
