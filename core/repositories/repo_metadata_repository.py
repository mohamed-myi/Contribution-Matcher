"""Repository metadata repository for caching."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_

from core.models import RepoMetadata

from .base import BaseRepository


class RepoMetadataRepository(BaseRepository[RepoMetadata]):
    """Repository for caching repository metadata."""

    model = RepoMetadata

    def get(self, repo_owner: str, repo_name: str) -> RepoMetadata | None:
        """Get cached metadata for a repository."""
        return (
            self.session.query(RepoMetadata)
            .filter(
                RepoMetadata.repo_owner == repo_owner,
                RepoMetadata.repo_name == repo_name,
            )
            .first()
        )

    def get_fresh(
        self,
        repo_owner: str,
        repo_name: str,
        validity_days: int = 7,
    ) -> RepoMetadata | None:
        """Get cached metadata if not stale. Returns None if cache is expired."""
        metadata = self.get(repo_owner, repo_name)
        if metadata and not metadata.is_stale(validity_days):
            return metadata
        return None

    def upsert(
        self,
        repo_owner: str,
        repo_name: str,
        stars: int | None = None,
        forks: int | None = None,
        languages: dict[str, int] | None = None,
        topics: list[str] | None = None,
        last_commit_date: str | None = None,
        contributor_count: int | None = None,
    ) -> RepoMetadata:
        """Insert or update repository metadata with auto-refresh of cached_at."""
        metadata = self.get(repo_owner, repo_name)

        if metadata:
            if stars is not None:
                metadata.stars = stars
            if forks is not None:
                metadata.forks = forks
            if languages is not None:
                metadata.languages = languages
            if topics is not None:
                metadata.topics = topics
            if last_commit_date is not None:
                metadata.last_commit_date = last_commit_date
            if contributor_count is not None:
                metadata.contributor_count = contributor_count
            metadata.cached_at = datetime.now(timezone.utc)
        else:
            metadata = RepoMetadata(
                repo_owner=repo_owner,
                repo_name=repo_name,
                stars=stars,
                forks=forks,
                languages=languages,
                topics=topics,
                last_commit_date=last_commit_date,
                contributor_count=contributor_count,
            )
            self.session.add(metadata)

        self.session.flush()
        return metadata

    def batch_get(self, repos: list[tuple[str, str]]) -> dict[tuple[str, str], RepoMetadata]:
        """
        Batch get metadata for multiple repositories in single query.

        Args:
            repos: List of (owner, name) tuples

        Returns:
            Dictionary mapping (owner, name) to metadata
        """
        if not repos:
            return {}

        conditions = [
            and_(RepoMetadata.repo_owner == owner, RepoMetadata.repo_name == name)
            for owner, name in repos
        ]

        results = self.session.query(RepoMetadata).filter(or_(*conditions)).all()

        return {(r.repo_owner, r.repo_name): r for r in results}

    def cleanup_stale(self, older_than_days: int = 30) -> int:
        """Remove cached metadata older than specified days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        result = self.session.query(RepoMetadata).filter(RepoMetadata.cached_at < cutoff).delete()
        self.session.flush()
        return result
