"""
Base model class for SQLAlchemy ORM.

Re-exports the Base class from the database module for convenience.
"""

from core.db import Base

__all__ = ["Base"]

