"""
Developer profile SQLAlchemy model.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


class DevProfile(Base):
    """
    Developer profile containing skills and preferences.
    
    Attributes:
        skills: List of technologies/skills the user knows
        experience_level: beginner, intermediate, or advanced
        interests: Areas of interest (e.g., "machine learning", "web development")
        preferred_languages: Programming languages the user prefers
        time_availability_hours_per_week: Weekly availability for contributions
    """
    __tablename__ = "dev_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    skills: Mapped[List[str]] = mapped_column(JSON, default=list)
    experience_level: Mapped[str] = mapped_column(String(50))
    interests: Mapped[List[str]] = mapped_column(JSON, default=list)
    preferred_languages: Mapped[List[str]] = mapped_column(JSON, default=list)
    time_availability_hours_per_week: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profile")

