"""
Base repository class with common CRUD operations.
"""

from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy.orm import Session

from core.db import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """
    Base repository providing common CRUD operations.
    
    Type parameter T is the SQLAlchemy model class.
    
    Usage:
        class UserRepository(BaseRepository[User]):
            pass
        
        repo = UserRepository(session)
        user = repo.get_by_id(1)
    """
    
    model: Type[T]
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, id: int) -> Optional[T]:
        """Get a single record by ID."""
        return self.session.query(self.model).filter(self.model.id == id).first()
    
    def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Get all records with pagination."""
        return (
            self.session.query(self.model)
            .offset(offset)
            .limit(limit)
            .all()
        )
    
    def create(self, **kwargs) -> T:
        """Create a new record."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        self.session.flush()  # Get ID without committing
        return instance
    
    def update(self, id: int, **kwargs) -> Optional[T]:
        """Update an existing record."""
        instance = self.get_by_id(id)
        if instance:
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            self.session.flush()
        return instance
    
    def delete(self, id: int) -> bool:
        """Delete a record by ID."""
        instance = self.get_by_id(id)
        if instance:
            self.session.delete(instance)
            self.session.flush()
            return True
        return False
    
    def count(self) -> int:
        """Get total count of records."""
        return self.session.query(self.model).count()
    
    def exists(self, id: int) -> bool:
        """Check if a record exists."""
        return self.session.query(
            self.session.query(self.model).filter(self.model.id == id).exists()
        ).scalar()

