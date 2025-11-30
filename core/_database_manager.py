"""
Unified Database Management Layer.

This module provides a singleton DatabaseManager that handles:
- Connection pooling (for PostgreSQL)
- Session management with context managers
- Auto-commit/rollback behavior
- Support for both SQLite and PostgreSQL

Usage:
    from core.database import db

    # Initialize (call once at app startup)
    db.initialize()

    # Use in context manager
    with db.session() as session:
        user = session.query(User).first()
        # Changes auto-committed on success, rolled back on exception

    # For FastAPI dependency injection
    def get_db():
        with db.session() as session:
            yield session
"""

from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from .config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""
    pass


class DatabaseManager:
    """
    Singleton database manager with connection pooling.
    
    Features:
    - Connection pooling for PostgreSQL (QueuePool)
    - StaticPool for SQLite (single connection)
    - Context manager for automatic commit/rollback
    - Thread-safe session factory
    """
    
    _instance: Optional["DatabaseManager"] = None
    
    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        # Prevent re-initialization
        pass
    
    def initialize(self, database_url: Optional[str] = None) -> None:
        """
        Initialize the database connection.
        
        Args:
            database_url: Optional database URL. If not provided, uses settings.
        
        Should be called once at application startup.
        """
        if self._initialized:
            return
        
        settings = get_settings()
        url = database_url or settings.database_url
        
        # Configure connection pool based on database type
        is_sqlite = url.startswith("sqlite")
        
        if is_sqlite:
            # SQLite needs StaticPool for thread safety in a single process
            # check_same_thread=False allows multi-threaded access
            connect_args = {"check_same_thread": False}
            pool_class = StaticPool
            pool_config = {}
        else:
            # PostgreSQL uses QueuePool for connection pooling
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
            **pool_config
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
        """Create all tables defined by the models."""
        if not self._initialized:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
        Base.metadata.create_all(bind=self.engine)
    
    def drop_all_tables(self) -> None:
        """Drop all tables. USE WITH CAUTION."""
        if not self._initialized:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
        Base.metadata.drop_all(bind=self.engine)
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.
        
        Automatically commits on success, rolls back on exception.
        
        Usage:
            with db.session() as session:
                user = session.query(User).first()
                user.name = "New Name"
                # Auto-commits on exit
        
        Yields:
            SQLAlchemy Session object
        """
        if not self._initialized:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
        
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
        Get a new session for manual management.
        
        Caller is responsible for commit/rollback/close.
        Prefer using session() context manager instead.
        
        Returns:
            SQLAlchemy Session object
        """
        if not self._initialized:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
        return self.SessionLocal()
    
    @property
    def is_initialized(self) -> bool:
        """Check if the database manager has been initialized."""
        return self._initialized
    
    def reset(self) -> None:
        """
        Reset the database manager state.
        
        Useful for testing. Disposes of engine and resets singleton.
        """
        if hasattr(self, 'engine') and self.engine:
            self.engine.dispose()
        self._initialized = False


# Global singleton instance
db = DatabaseManager()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.
    
    Usage in FastAPI:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    with db.session() as session:
        yield session

