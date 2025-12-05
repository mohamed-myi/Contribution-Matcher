"""
Issue-related SQLAlchemy models.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


class Issue(Base):
    """
    GitHub issue model with repository metadata.
    
    Represents an open-source issue that users can match with.
    Includes repository metadata for scoring and filtering.
    """
    __tablename__ = "issues"
    __table_args__ = (
        UniqueConstraint("user_id", "url", name="uq_issues_user_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(512))
    body: Mapped[Optional[str]] = mapped_column(Text)
    repo_owner: Mapped[Optional[str]] = mapped_column(String(255))
    repo_name: Mapped[Optional[str]] = mapped_column(String(255))
    repo_url: Mapped[Optional[str]] = mapped_column(String(512))
    difficulty: Mapped[Optional[str]] = mapped_column(String(64))
    issue_type: Mapped[Optional[str]] = mapped_column(String(64))
    time_estimate: Mapped[Optional[str]] = mapped_column(String(64))
    labels: Mapped[Optional[List[str]]] = mapped_column(JSON)
    repo_stars: Mapped[Optional[int]] = mapped_column(Integer)
    repo_forks: Mapped[Optional[int]] = mapped_column(Integer)
    repo_languages: Mapped[Optional[Dict]] = mapped_column(JSON)
    repo_topics: Mapped[Optional[List[str]]] = mapped_column(JSON)
    last_commit_date: Mapped[Optional[str]] = mapped_column(String(64))
    contributor_count: Mapped[Optional[int]] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    label: Mapped[Optional[str]] = mapped_column(String(16))
    labeled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Precomputed score cache (added for performance - Phase 1)
    cached_score: Mapped[Optional[float]] = mapped_column(Float)
    
    # Staleness tracking (Phase 2)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    close_reason: Mapped[Optional[str]] = mapped_column(String(32))  # 'completed', 'not_planned', 'merged', etc.
    github_state: Mapped[Optional[str]] = mapped_column(String(16))  # 'open', 'closed'

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="issues")
    technologies: Mapped[List["IssueTechnology"]] = relationship(
        "IssueTechnology", back_populates="issue", cascade="all, delete-orphan"
    )
    bookmarks: Mapped[List["IssueBookmark"]] = relationship(
        "IssueBookmark", back_populates="issue", cascade="all, delete-orphan"
    )
    labels_relationship: Mapped[List["IssueLabel"]] = relationship(
        "IssueLabel", back_populates="issue", cascade="all, delete-orphan"
    )
    embeddings: Mapped["IssueEmbedding"] = relationship(
        "IssueEmbedding", back_populates="issue", uselist=False, cascade="all, delete-orphan"
    )
    feature_cache: Mapped["IssueFeatureCache"] = relationship(
        "IssueFeatureCache", back_populates="issue", uselist=False, cascade="all, delete-orphan"
    )
    notes: Mapped[List["IssueNote"]] = relationship(
        "IssueNote", back_populates="issue", cascade="all, delete-orphan"
    )
    
    def to_dict(self) -> Dict:
        """
        Convert the issue record into a serializable dictionary.

        Returns:
            Dictionary compatible with API responses and scoring pipelines.
        """
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "body": self.body,
            "repo_owner": self.repo_owner,
            "repo_name": self.repo_name,
            "repo_url": self.repo_url,
            "difficulty": self.difficulty,
            "issue_type": self.issue_type,
            "time_estimate": self.time_estimate,
            "labels": self.labels,
            "repo_stars": self.repo_stars,
            "repo_forks": self.repo_forks,
            "repo_languages": self.repo_languages,
            "repo_topics": self.repo_topics,
            "last_commit_date": self.last_commit_date,
            "contributor_count": self.contributor_count,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "cached_score": self.cached_score,
            "last_verified_at": self.last_verified_at.isoformat() if self.last_verified_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "close_reason": self.close_reason,
            "github_state": self.github_state,
        }
    
    @property
    def is_stale(self) -> bool:
        """Check if issue needs re-verification (not verified in 7+ days)."""
        if not self.last_verified_at:
            return True
        days_since_verified = (datetime.utcnow() - self.last_verified_at).days
        return days_since_verified >= 7
    
    @property
    def is_very_stale(self) -> bool:
        """Check if issue is very stale (not verified in 30+ days)."""
        if not self.last_verified_at:
            return True
        days_since_verified = (datetime.utcnow() - self.last_verified_at).days
        return days_since_verified >= 30


class IssueTechnology(Base):
    """
    Technologies/skills associated with an issue.
    
    Extracted from issue title, body, and repo languages.
    """
    __tablename__ = "issue_technologies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"))
    technology: Mapped[str] = mapped_column(String(255), index=True)
    technology_category: Mapped[Optional[str]] = mapped_column(String(255))

    issue: Mapped[Issue] = relationship("Issue", back_populates="technologies")


class IssueBookmark(Base):
    """
    User bookmarks for issues they want to track.
    """
    __tablename__ = "issue_bookmarks"
    __table_args__ = (
        UniqueConstraint("user_id", "issue_id", name="uq_issue_bookmarks_user_issue"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="bookmarks")
    issue: Mapped[Issue] = relationship("Issue", back_populates="bookmarks")


class IssueLabel(Base):
    """
    User-provided quality labels for ML training.
    
    Labels issues as 'good' or 'bad' matches for the user.
    """
    __tablename__ = "issue_labels"
    __table_args__ = (
        UniqueConstraint("user_id", "issue_id", name="uq_issue_labels_user_issue"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(8))  # 'good' or 'bad'
    labeled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="labels")
    issue: Mapped[Issue] = relationship("Issue", back_populates="labels_relationship")


class IssueEmbedding(Base):
    """
    Cached BERT embeddings for semantic similarity.
    """
    __tablename__ = "issue_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), unique=True, index=True
    )
    description_embedding: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    title_embedding: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    embedding_model: Mapped[str] = mapped_column(String(255), default="all-MiniLM-L6-v2")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    issue: Mapped[Issue] = relationship("Issue", back_populates="embeddings")


class IssueFeatureCache(Base):
    """
    Cached feature vectors for scoring.
    
    Stores precomputed feature values to avoid recalculation.
    Invalidated when profile or issue is updated.
    """
    __tablename__ = "issue_feature_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), unique=True, index=True
    )
    profile_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    issue_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    skill_match_pct: Mapped[Optional[float]] = mapped_column(Float)
    experience_score: Mapped[Optional[float]] = mapped_column(Float)
    repo_quality_score: Mapped[Optional[float]] = mapped_column(Float)
    freshness_score: Mapped[Optional[float]] = mapped_column(Float)
    time_match_score: Mapped[Optional[float]] = mapped_column(Float)
    interest_match_score: Mapped[Optional[float]] = mapped_column(Float)
    total_score: Mapped[Optional[float]] = mapped_column(Float)
    feature_vector: Mapped[Optional[Dict]] = mapped_column(JSON)

    issue: Mapped[Issue] = relationship("Issue", back_populates="feature_cache")


class IssueNote(Base):
    """
    User notes on issues for personal tracking.
    """
    __tablename__ = "issue_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship("User")
    issue: Mapped[Issue] = relationship("Issue", back_populates="notes")

