"""
Unified Database Management Layer.

Provides a singleton DatabaseManager for:
- Connection pooling (PostgreSQL) / StaticPool (SQLite)
- Session management with context managers
- Auto-commit/rollback behavior

Usage:
    from core.db import db, get_db, Base

    db.initialize()
    with db.session() as session:
        user = session.query(User).first()
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from .config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""

    pass


class DatabaseManager:
    """
    Singleton database manager with connection pooling and health checks.

    Features:
    - Connection pooling (QueuePool for PostgreSQL, StaticPool for SQLite)
    - Context manager for automatic commit/rollback
    - Thread-safe session factory
    - Health check support
    """

    _instance: Optional["DatabaseManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        pass  # Prevent re-initialization

    def initialize(self, database_url: str | None = None) -> None:
        """
        Initialize database connection. Call once at app startup.

        Args:
            database_url: Optional override. Uses settings.database_url if not provided.
        """
        if self._initialized:
            return

        settings = get_settings()
        url = database_url or settings.database_url
        is_sqlite = url.startswith("sqlite")

        if is_sqlite:
            connect_args = {"check_same_thread": False}
            pool_class: type[StaticPool | QueuePool] = StaticPool
            pool_config = {}
        else:
            connect_args = {}
            pool_class = QueuePool
            pool_config = {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_pre_ping": settings.db_pool_pre_ping,
            }

        self.engine = create_engine(
            url,
            poolclass=pool_class,
            connect_args=connect_args,
            echo=settings.debug,
            future=True,
            **pool_config,
        )

        # Enable foreign keys for SQLite
        if is_sqlite:

            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )

        self._initialized = True

    def create_all_tables(self) -> None:
        """Create all tables defined by models."""
        self._ensure_initialized()
        Base.metadata.create_all(bind=self.engine)

    def drop_all_tables(self) -> None:
        """Drop all tables. USE WITH CAUTION."""
        self._ensure_initialized()
        Base.metadata.drop_all(bind=self.engine)

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions with auto-commit/rollback.

        Usage:
            with db.session() as session:
                user = session.query(User).first()
        """
        self._ensure_initialized()
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session(self) -> Session:
        """
        Get session for manual management. Prefer session() context manager.
        Caller is responsible for commit/rollback/close.
        """
        self._ensure_initialized()
        return self.SessionLocal()

    @property
    def is_initialized(self) -> bool:
        """Check if database manager is initialized."""
        return self._initialized

    def health_check(self) -> dict:
        """
        Perform database health check.

        Returns:
            dict with 'healthy' (bool), 'latency_ms' (float), and 'error' (str or None)
        """
        import time

        if not self._initialized:
            return {"healthy": False, "latency_ms": 0, "error": "Database not initialized"}

        start = time.perf_counter()
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            latency = (time.perf_counter() - start) * 1000
            return {"healthy": True, "latency_ms": round(latency, 2), "error": None}
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return {"healthy": False, "latency_ms": round(latency, 2), "error": str(e)}

    def get_pool_status(self) -> dict:
        """
        Get connection pool status (PostgreSQL only).

        Returns:
            dict with pool statistics or empty dict for SQLite
        """
        if not self._initialized:
            return {}

        pool = self.engine.pool
        if isinstance(pool, StaticPool):
            return {"type": "StaticPool", "note": "Single connection (SQLite)"}

        if isinstance(pool, QueuePool):
            return {
                "type": "QueuePool",
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
            }

        # Fallback for other pool types
        return {"type": type(pool).__name__}

    def reset(self) -> None:
        """Reset database manager. Disposes engine and clears singleton state."""
        if hasattr(self, "engine") and self.engine:
            self.engine.dispose()
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Raise error if not initialized."""
        if not self._initialized:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")


# Global singleton
db = DatabaseManager()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.

    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    with db.session() as session:
        yield session


__all__ = ["Base", "DatabaseManager", "db", "get_db"]
