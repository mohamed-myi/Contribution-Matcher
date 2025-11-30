"""
Database session and base configuration.

This module provides backward compatibility with the existing backend code.
It re-exports from the unified core.db module.

For new code, prefer importing directly from core.db:
    from core.db import db, get_db, Base
"""

# Re-export from core.db for backward compatibility
from core.db import Base, db, get_db

# Initialize the database if not already done
if not db.is_initialized:
    from core.config import get_settings
    settings = get_settings()
    db.initialize(settings.database_url)

# For backward compatibility, expose engine and SessionLocal
engine = db.engine if db.is_initialized else None
SessionLocal = db.SessionLocal if db.is_initialized else None

