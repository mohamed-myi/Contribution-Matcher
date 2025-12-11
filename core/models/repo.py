"""
Repository metadata SQLAlchemy model.

Used for caching repository information to reduce GitHub API calls.
"""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import DateTime, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class RepoMetadata(Base):
    """
    Cached repository metadata.

    Reduces GitHub API calls by caching repo information.
    Cache validity is controlled by CACHE_VALIDITY_DAYS setting.
    """

    __tablename__ = "repo_metadata"
    __table_args__ = (
        UniqueConstraint("repo_owner", "repo_name", name="uq_repo_metadata_owner_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_owner: Mapped[str] = mapped_column(String(255), index=True)
    repo_name: Mapped[str] = mapped_column(String(255), index=True)
    stars: Mapped[Optional[int]] = mapped_column(Integer)
    forks: Mapped[Optional[int]] = mapped_column(Integer)
    languages: Mapped[Optional[Dict[str, int]]] = mapped_column(JSON)
    topics: Mapped[Optional[List[str]]] = mapped_column(JSON)
    last_commit_date: Mapped[Optional[str]] = mapped_column(String(64))
    contributor_count: Mapped[Optional[int]] = mapped_column(Integer)
    cached_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def is_stale(self, validity_days: int = 7) -> bool:
        """
        Determine whether cached metadata has exceeded its validity window.

        Args:
            validity_days: Number of days before cache should be refreshed.

        Returns:
            True if cache is older than validity_days; otherwise False.
        """
        from datetime import timedelta

        if not self.cached_at:
            return True
        age = datetime.utcnow() - self.cached_at
        return age > timedelta(days=validity_days)

    def to_dict(self) -> Dict:
        """
        Serialize the repository metadata for downstream consumers.

        Returns:
            Dictionary of repository attributes and cache timestamp.
        """
        return {
            "stars": self.stars,
            "forks": self.forks,
            "languages": self.languages,
            "topics": self.topics,
            "last_commit_date": self.last_commit_date,
            "contributor_count": self.contributor_count,
            "cached_at": self.cached_at.isoformat() if self.cached_at else None,
        }
