"""
Scoring Service.

Business logic for issue scoring.
"""

from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from core.models import DevProfile, Issue
from core.repositories import IssueRepository, ProfileRepository


class ScoringService:
    """Service for scoring issues against user profiles."""
    
    def __init__(self, session: Session):
        self.session = session
        self.issue_repo = IssueRepository(session)
        self.profile_repo = ProfileRepository(session)
    
    def get_top_matches(
        self,
        user_id: int,
        limit: int = 10,
    ) -> List[Dict]:
        """
        Get top-scored issues for a user.
        
        Uses cached scores when available.
        """
        issues = self.issue_repo.get_top_scored(user_id, limit)
        
        return [
            {
                "issue_id": issue.id,
                "issue_title": issue.title,
                "repo_name": f"{issue.repo_owner}/{issue.repo_name}" if issue.repo_owner else None,
                "url": issue.url,
                "score": issue.cached_score or 0,
                "breakdown": {},  # Full breakdown requires recalculation
            }
            for issue in issues
        ]
    
    def score_issue(
        self,
        user_id: int,
        issue_id: int,
        use_ml: bool = True,
    ) -> Dict:
        """Score a single issue against user's profile."""
        from core.scoring.issue_scorer import score_issue_against_profile
        
        issue = self.issue_repo.get_by_id(issue_id, user_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")
        
        profile = self.profile_repo.get_by_user_id(user_id)
        if not profile:
            raise ValueError("User profile not found")
        
        profile_dict = {
            "skills": profile.skills or [],
            "experience_level": profile.experience_level,
            "interests": profile.interests or [],
            "preferred_languages": profile.preferred_languages or [],
            "time_availability_hours_per_week": profile.time_availability_hours_per_week,
        }
        
        issue_dict = issue.to_dict()
        
        return score_issue_against_profile(profile_dict, issue_dict, session=self.session)
    
    def score_all_issues(
        self,
        user_id: int,
        limit: int = 100,
    ) -> List[Dict]:
        """Score all active issues for a user."""
        from core.scoring.issue_scorer import score_issue_against_profile
        
        profile = self.profile_repo.get_by_user_id(user_id)
        if not profile:
            return []
        
        profile_dict = {
            "skills": profile.skills or [],
            "experience_level": profile.experience_level,
            "interests": profile.interests or [],
            "preferred_languages": profile.preferred_languages or [],
            "time_availability_hours_per_week": profile.time_availability_hours_per_week,
        }
        
        issues = self.issue_repo.get_batch(user_id, limit=limit)
        
        scores = []
        score_updates = {}
        
        for issue in issues:
            try:
                issue_dict = issue.to_dict()
                result = score_issue_against_profile(profile_dict, issue_dict, session=self.session)
                scores.append(result)
                score_updates[issue.id] = result.get("score", 0)
            except Exception:
                continue
        
        # Update cached scores
        if score_updates:
            self.issue_repo.update_cached_scores(score_updates)
        
        # Sort by score
        scores.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return scores
    
    def invalidate_scores(self, user_id: int) -> int:
        """
        Invalidate cached scores for a user.
        
        Call this when profile changes.
        """
        result = self.session.query(Issue).filter(
            Issue.user_id == user_id,
            Issue.cached_score.isnot(None),
        ).update({"cached_score": None}, synchronize_session=False)
        self.session.flush()
        return result
