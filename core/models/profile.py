"""
Developer profile SQLAlchemy model.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


# Profile source constants
PROFILE_SOURCE_GITHUB = "github"
PROFILE_SOURCE_RESUME = "resume"
PROFILE_SOURCE_MANUAL = "manual"


class DevProfile(Base):
    """
    Developer profile containing skills and preferences.

    Attributes:
        skills: List of technologies/skills the user knows
        experience_level: beginner, intermediate, or advanced
        interests: Areas of interest (e.g., "machine learning", "web development")
        preferred_languages: Programming languages the user prefers
        time_availability_hours_per_week: Weekly availability for contributions
        profile_source: Origin of profile data ("github", "resume", "manual")
        last_github_sync: Timestamp of last GitHub profile sync
    """

    __tablename__ = "dev_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    experience_level: Mapped[str] = mapped_column(String(50))
    interests: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_languages: Mapped[list[str]] = mapped_column(JSON, default=list)
    time_availability_hours_per_week: Mapped[int | None] = mapped_column(Integer)

    # Profile source tracking (default to GitHub for new users)
    profile_source: Mapped[str] = mapped_column(
        String(20), default=PROFILE_SOURCE_GITHUB, nullable=False
    )
    last_github_sync: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profile")

    @property
    def is_from_github(self) -> bool:
        """Check if profile was created from GitHub."""
        return self.profile_source == PROFILE_SOURCE_GITHUB

    @property
    def is_from_resume(self) -> bool:
        """Check if profile was created from resume."""
        return self.profile_source == PROFILE_SOURCE_RESUME

    @property
    def is_manual(self) -> bool:
        """Check if profile was manually created/edited."""
        return self.profile_source == PROFILE_SOURCE_MANUAL
