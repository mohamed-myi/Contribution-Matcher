"""
User-related SQLAlchemy models.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .issue import Issue, IssueBookmark, IssueLabel
    from .ml import UserMLModel
    from .profile import DevProfile


class User(Base):
    """
    User model representing authenticated GitHub users.

    Attributes:
        github_id: Unique GitHub user ID
        github_username: GitHub username
        email: User email (optional)
        avatar_url: GitHub avatar URL
        github_access_token: OAuth access token for GitHub API
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    github_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    github_username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    github_access_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    profile: Mapped["DevProfile"] = relationship("DevProfile", back_populates="user", uselist=False)
    issues: Mapped[list["Issue"]] = relationship("Issue", back_populates="user")
    bookmarks: Mapped[list["IssueBookmark"]] = relationship("IssueBookmark", back_populates="user")
    labels: Mapped[list["IssueLabel"]] = relationship("IssueLabel", back_populates="user")
    ml_models: Mapped[list["UserMLModel"]] = relationship("UserMLModel", back_populates="user")


class TokenBlacklist(Base):
    """
    Store invalidated JWT tokens until they expire.

    Used for logout functionality to invalidate tokens before expiry.
    """

    __tablename__ = "token_blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_jti: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
