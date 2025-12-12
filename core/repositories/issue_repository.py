"""
Issue repository with batch operations and efficient queries.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import selectinload

from core.models import Issue, IssueBookmark, IssueTechnology

from .base import BaseRepository


class IssueRepository(BaseRepository[Issue]):
    """
    Repository for Issue operations with optimized batch queries.

    Key features:
    - list_with_bookmarks: Efficient 2-query pattern (not N+1)
    - bulk_upsert: Single transaction for multiple issues
    - Eager loading of relationships
    """

    model = Issue

    def get_by_id(self, issue_id: int, user_id: int) -> Issue | None:  # type: ignore[override]
        """Get an issue by ID for a specific user."""
        return (
            self.session.query(Issue)
            .filter(
                Issue.id == issue_id,
                Issue.user_id == user_id,
                Issue.is_active,
            )
            .first()
        )

    def get_by_url(self, user_id: int, url: str) -> Issue | None:
        """Get an issue by its URL for a specific user."""
        return self.session.query(Issue).filter(Issue.user_id == user_id, Issue.url == url).first()

    def list_with_bookmarks(
        self,
        user_id: int,
        filters: dict,
        offset: int = 0,
        limit: int = 20,
        skip_count: bool = False,
    ) -> tuple[list[Issue], int, set[int]]:
        """
        Get issues with bookmark status efficiently.

        Uses 2-3 queries instead of N+1:
        1. Main query with eager loading
        2. Optimized count (optional, uses subquery)
        3. Batch fetch bookmark IDs

        Args:
            user_id: User ID
            filters: Filter dictionary with keys:
                - difficulty: Filter by difficulty level
                - technology: Filter by technology
                - language: Filter by repo language
                - issue_type: Filter by issue type
                - days_back: Only issues created within N days
                - is_active: Filter by active status
            offset: Pagination offset
            limit: Pagination limit
            skip_count: Skip total count query (for infinite scroll)

        Returns:
            Tuple of (issues, total_count, bookmarked_issue_ids)
        """
        # Build base filter conditions (reused for both count and select)
        base_conditions = [Issue.user_id == user_id]

        if filters.get("difficulty"):
            base_conditions.append(Issue.difficulty == filters["difficulty"])

        if filters.get("issue_type"):
            base_conditions.append(Issue.issue_type == filters["issue_type"])

        if filters.get("days_back"):
            cutoff = datetime.now(timezone.utc) - timedelta(days=filters["days_back"])
            base_conditions.append(Issue.created_at >= cutoff)

        if filters.get("is_active") is not None:
            base_conditions.append(Issue.is_active == filters["is_active"])

        if filters.get("language"):
            lang = filters["language"]
            # Use JSON key extraction for proper language filtering
            # This works with SQLite's JSON functions
            base_conditions.append(
                func.json_extract(Issue.repo_languages, f'$."{lang}"').isnot(None)
            )

        if filters.get("min_stars"):
            base_conditions.append(Issue.repo_stars >= filters["min_stars"])

        if filters.get("score_range"):
            score_range = filters["score_range"]
            if score_range == "high":
                base_conditions.append(Issue.cached_score >= 80)
            elif score_range == "medium":
                base_conditions.append(Issue.cached_score >= 50)
                base_conditions.append(Issue.cached_score < 80)
            elif score_range == "low":
                base_conditions.append(Issue.cached_score < 50)

        # Build main query with eager loading
        query = (
            self.session.query(Issue)
            .options(selectinload(Issue.technologies))
            .filter(and_(*base_conditions))
        )

        # Technology filter requires join
        if filters.get("technology"):
            tech = filters["technology"]
            query = query.join(Issue.technologies).filter(
                IssueTechnology.technology.ilike(f"%{tech}%")
            )

        # Optimized count - use COUNT(*) with same filters but no eager loading
        if skip_count:
            total = -1  # Signal that count was skipped
        else:
            count_query = self.session.query(func.count(Issue.id)).filter(and_(*base_conditions))
            if filters.get("technology"):
                tech = filters["technology"]
                count_query = count_query.join(Issue.technologies).filter(
                    IssueTechnology.technology.ilike(f"%{tech}%")
                )
            total = count_query.scalar()

        # Get paginated results ordered by cached_score or created_at
        if filters.get("order_by") == "score":
            query = query.order_by(Issue.cached_score.desc().nullslast())
        else:
            query = query.order_by(Issue.created_at.desc())

        issues = query.offset(offset).limit(limit).all()

        # Batch load bookmark statuses (single query)
        if issues:
            issue_ids = [i.id for i in issues]
            bookmarked_ids = {
                row[0]
                for row in self.session.query(IssueBookmark.issue_id)
                .filter(
                    IssueBookmark.user_id == user_id,
                    IssueBookmark.issue_id.in_(issue_ids),
                )
                .all()
            }
        else:
            bookmarked_ids = set()

        return issues, total, bookmarked_ids

    def bulk_upsert(
        self,
        user_id: int,
        issues_data: list[dict],
    ) -> list[Issue]:
        """
        Batch insert/update issues with single commit.

        Issues are matched by URL for upsert behavior.
        Technologies are replaced for each issue.

        Args:
            user_id: User ID
            issues_data: List of issue dictionaries with keys matching Issue model
                Each dict may have 'technologies' key with list of (tech, category) tuples

        Returns:
            List of created/updated Issue objects
        """
        results = []

        for data in issues_data:
            # Extract technologies before creating/updating issue
            technologies = data.pop("technologies", [])
            url = data.get("url")

            if not url:
                continue

            # Find existing or create new
            issue = self.get_by_url(user_id, url)

            if not issue:
                issue = Issue(user_id=user_id, url=url)
                self.session.add(issue)

            # Update fields
            for key, value in data.items():
                if key != "url" and hasattr(issue, key):
                    setattr(issue, key, value)

            # Flush to get ID for new issues
            self.session.flush()

            # Replace technologies
            if technologies:
                # Clear existing
                self.session.query(IssueTechnology).filter(
                    IssueTechnology.issue_id == issue.id
                ).delete()

                # Add new
                for tech, category in technologies:
                    self.session.add(
                        IssueTechnology(
                            issue_id=issue.id,
                            technology=tech,
                            technology_category=category,
                        )
                    )

            results.append(issue)

        # Single flush for all
        self.session.flush()
        return results

    def get_batch(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Issue]:
        """Get a batch of issues for processing (e.g., scoring)."""
        return (
            self.session.query(Issue)
            .filter(Issue.user_id == user_id, Issue.is_active)
            .order_by(Issue.id)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_top_scored(
        self,
        user_id: int,
        limit: int = 10,
    ) -> list[Issue]:
        """Get top-scored issues using cached_score."""
        return (
            self.session.query(Issue)
            .options(selectinload(Issue.technologies))
            .filter(
                Issue.user_id == user_id,
                Issue.is_active,
                Issue.cached_score.isnot(None),
            )
            .order_by(Issue.cached_score.desc())
            .limit(limit)
            .all()
        )

    def update_cached_scores(self, scores: dict[int, float]) -> int:
        """
        Bulk update cached_score for multiple issues.

        Uses efficient bulk update with CASE statement instead of individual updates.

        Args:
            scores: Dictionary mapping issue_id to score

        Returns:
            Number of issues updated
        """
        if not scores:
            return 0

        from sqlalchemy import case

        # Build CASE expression for bulk update
        case_stmt = case(dict(scores.items()), value=Issue.id)

        result = (
            self.session.query(Issue)
            .filter(Issue.id.in_(scores.keys()))
            .update({"cached_score": case_stmt}, synchronize_session=False)
        )

        self.session.flush()
        return result

    def mark_stale(
        self,
        user_id: int,
        issue_ids: list[int],
    ) -> int:
        """Mark issues as inactive (stale)."""
        if not issue_ids:
            return 0

        result = (
            self.session.query(Issue)
            .filter(
                Issue.user_id == user_id,
                Issue.id.in_(issue_ids),
            )
            .update({"is_active": False}, synchronize_session=False)
        )
        self.session.flush()
        return result

    def get_variety_stats(self, user_id: int) -> dict:
        """Get statistics about issue variety for a user."""
        base_query = self.session.query(Issue).filter(
            Issue.user_id == user_id,
            Issue.is_active,
        )

        # Count by difficulty
        difficulty_results = (
            base_query.with_entities(Issue.difficulty, func.count(Issue.id))
            .group_by(Issue.difficulty)
            .all()
        )
        difficulty_counts: dict[str | None, int] = {row[0]: row[1] for row in difficulty_results}

        # Count by issue type
        type_results = (
            base_query.with_entities(Issue.issue_type, func.count(Issue.id))
            .group_by(Issue.issue_type)
            .all()
        )
        type_counts: dict[str | None, int] = {row[0]: row[1] for row in type_results}

        # Total count
        total = base_query.count()

        return {
            "total": total,
            "by_difficulty": difficulty_counts,
            "by_type": type_counts,
        }

    def get_active_issue_urls(
        self,
        user_id: int,
        limit: int = 100,
    ) -> list[str]:
        """Get URLs of active issues for status checking."""
        results = (
            self.session.query(Issue.url)
            .filter(
                Issue.user_id == user_id,
                Issue.is_active,
                Issue.url.isnot(None),
            )
            .order_by(Issue.updated_at)  # Check oldest first
            .limit(limit)
            .all()
        )
        return [row[0] for row in results]

    def mark_inactive(self, urls: list[str]) -> int:
        """Mark issues as inactive by URL."""
        if not urls:
            return 0

        result = (
            self.session.query(Issue)
            .filter(Issue.url.in_(urls))
            .update({"is_active": False}, synchronize_session=False)
        )
        self.session.flush()
        return result

    def get_unscored(
        self,
        user_id: int,
        limit: int = 100,
    ) -> list[Issue]:
        """Get issues that don't have a cached score."""
        return (
            self.session.query(Issue)
            .options(selectinload(Issue.technologies))
            .filter(
                Issue.user_id == user_id,
                Issue.is_active,
                or_(
                    Issue.cached_score.is_(None),
                    Issue.cached_score == 0,
                ),
            )
            .limit(limit)
            .all()
        )
