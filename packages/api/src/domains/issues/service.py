"""
Issue Service.

Business logic for issue operations.
"""

from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from core.models import Issue, IssueBookmark, IssueTechnology
from core.repositories import IssueRepository


class IssueService:
    """Service for issue-related business logic."""
    
    def __init__(self, session: Session):
        self.session = session
        self.repository = IssueRepository(session)
    
    def get_issues(
        self,
        user_id: int,
        filters: Dict,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Issue], int, Set[int]]:
        """
        Get issues with filters and bookmark status.
        
        Returns:
            Tuple of (issues, total_count, bookmarked_issue_ids)
        """
        return self.repository.list_with_bookmarks(
            user_id=user_id,
            filters=filters,
            offset=offset,
            limit=limit,
        )
    
    def get_issue_by_id(self, user_id: int, issue_id: int) -> Optional[Issue]:
        """Get a single issue by ID."""
        return self.repository.get_by_id(issue_id, user_id)
    
    def create_issues(
        self,
        user_id: int,
        issues_data: List[Dict],
    ) -> List[Issue]:
        """Create or update multiple issues."""
        return self.repository.bulk_upsert(user_id, issues_data)
    
    def toggle_bookmark(self, user_id: int, issue_id: int) -> bool:
        """
        Toggle bookmark status for an issue.
        
        Returns:
            True if bookmarked, False if unbookmarked.
        """
        existing = self.session.query(IssueBookmark).filter(
            IssueBookmark.user_id == user_id,
            IssueBookmark.issue_id == issue_id,
        ).first()
        
        if existing:
            self.session.delete(existing)
            self.session.flush()
            return False
        else:
            bookmark = IssueBookmark(user_id=user_id, issue_id=issue_id)
            self.session.add(bookmark)
            self.session.flush()
            return True
    
    def get_bookmarked_issues(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Issue], int]:
        """Get user's bookmarked issues."""
        from sqlalchemy import func
        
        # Count query
        total = self.session.query(func.count(IssueBookmark.id)).filter(
            IssueBookmark.user_id == user_id
        ).scalar()
        
        # Get bookmarked issue IDs
        bookmarks = self.session.query(IssueBookmark.issue_id).filter(
            IssueBookmark.user_id == user_id
        ).order_by(IssueBookmark.created_at.desc()).offset(offset).limit(limit).all()
        
        issue_ids = [b[0] for b in bookmarks]
        
        if not issue_ids:
            return [], total
        
        # Get issues
        issues = self.session.query(Issue).filter(
            Issue.id.in_(issue_ids)
        ).all()
        
        # Maintain order
        issue_map = {i.id: i for i in issues}
        ordered_issues = [issue_map[iid] for iid in issue_ids if iid in issue_map]
        
        return ordered_issues, total
    
    def mark_issues_inactive(self, user_id: int, issue_ids: List[int]) -> int:
        """Mark issues as inactive (closed/stale)."""
        return self.repository.mark_stale(user_id, issue_ids)
    
    def get_issue_technologies(self, issue_id: int) -> List[str]:
        """Get technology list for an issue."""
        techs = self.session.query(IssueTechnology).filter(
            IssueTechnology.issue_id == issue_id
        ).all()
        return [t.technology for t in techs]
    
    def get_statistics(self, user_id: int) -> Dict:
        """Get issue statistics for a user."""
        from sqlalchemy import func
        
        total = self.session.query(func.count(Issue.id)).filter(
            Issue.user_id == user_id
        ).scalar()
        
        active = self.session.query(func.count(Issue.id)).filter(
            Issue.user_id == user_id,
            Issue.is_active == True,
        ).scalar()
        
        labeled = self.session.query(func.count(Issue.id)).filter(
            Issue.user_id == user_id,
            Issue.label.isnot(None),
        ).scalar()
        
        bookmarked = self.session.query(func.count(IssueBookmark.id)).filter(
            IssueBookmark.user_id == user_id
        ).scalar()
        
        by_difficulty = dict(
            self.session.query(Issue.difficulty, func.count(Issue.id))
            .filter(Issue.user_id == user_id, Issue.is_active == True)
            .group_by(Issue.difficulty)
            .all()
        )
        
        return {
            "total": total,
            "active": active,
            "labeled": labeled,
            "bookmarked": bookmarked,
            "by_difficulty": by_difficulty,
        }
