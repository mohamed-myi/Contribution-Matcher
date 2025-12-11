"""
Database session and base configuration.

This module provides backward compatibility with the existing backend code.
It re-exports from the unified core.db module.

For new code, prefer importing directly from core.db:
    from core.db import db, get_db, Base

Note: Database initialization is now handled explicitly in main.py startup,
NOT at import time. This prevents issues with configuration loading order
and allows proper health checking before database access.
"""

# Re-export from core.db for backward compatibility
from core.db import db


class _LazyEngine:
    """Lazy wrapper for database engine that checks initialization."""

    def __getattr__(self, name):
        if not db.is_initialized:
            raise RuntimeError(
                "Database not initialized. Call db.initialize() in application startup."
            )
        return getattr(db.engine, name)


class _LazySessionLocal:
    """Lazy wrapper for SessionLocal that checks initialization."""

    def __call__(self, *args, **kwargs):
        if not db.is_initialized:
            raise RuntimeError(
                "Database not initialized. Call db.initialize() in application startup."
            )
        return db.SessionLocal(*args, **kwargs)


# For backward compatibility - lazy proxies that check initialization
engine = _LazyEngine()
SessionLocal = _LazySessionLocal()
