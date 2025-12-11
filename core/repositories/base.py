"""Base repository class with common CRUD operations."""

from typing import Generic, TypeVar

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.db import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """
    Base repository providing common CRUD operations.

    Usage:
        class UserRepository(BaseRepository[User]):
            model = User

        repo = UserRepository(session)
        user = repo.get_by_id(1)
    """

    model: type[T]

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, id: int) -> T | None:
        """Get a single record by ID."""
        return self.session.get(self.model, id)

    def get_all(self, limit: int = 100, offset: int = 0) -> list[T]:
        """Get all records with pagination."""
        return self.session.query(self.model).offset(offset).limit(limit).all()

    def create(self, **kwargs) -> T:
        """Create a new record."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        self.session.flush()
        return instance

    def update(self, id: int, **kwargs) -> T | None:
        """Update an existing record."""
        instance = self.get_by_id(id)
        if instance:
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            self.session.flush()
        return instance

    def bulk_update(self, ids: list[int], **kwargs) -> int:
        """Bulk update multiple records with same values."""
        if not ids:
            return 0
        result = (
            self.session.query(self.model)
            .filter(self.model.id.in_(ids))  # type: ignore[attr-defined]
            .update(kwargs, synchronize_session=False)  # type: ignore[arg-type]
        )
        self.session.flush()
        return result

    def delete(self, id: int) -> bool:
        """Delete a record by ID."""
        instance = self.get_by_id(id)
        if instance:
            self.session.delete(instance)
            self.session.flush()
            return True
        return False

    def count(self, **filters) -> int:
        """Get count of records, optionally filtered."""
        query = self.session.query(func.count(self.model.id))  # type: ignore[attr-defined]
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        return query.scalar() or 0

    def exists(self, id: int) -> bool:
        """Check if a record exists."""
        result = self.session.query(
            self.session.query(self.model).filter(self.model.id == id).exists()  # type: ignore[attr-defined]
        ).scalar()
        return bool(result) if result is not None else False

    def exists_where(self, **filters) -> bool:
        """Check if any record exists matching filters."""
        query = self.session.query(self.model)
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        result = self.session.query(query.exists()).scalar()
        return bool(result) if result is not None else False
