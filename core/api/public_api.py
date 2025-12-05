"""
Public API for programmatic use of Contribution Matcher.

This module provides high-level functions for issue discovery, scoring, and profile management.
All functions require user_id for multi-user support.
"""

from typing import Dict, List, Optional

from core.api.github_api import search_issues, get_repo_metadata_from_api
from core.parsing import parse_issue
from core.parsing.skill_extractor import analyze_job_text
from core.profile import load_dev_profile, save_dev_profile
from core.scoring import (
    score_issue_against_profile,
    score_profile_against_all_issues,
    get_top_matches,
    train_model as train_ml_model,
)


def _ensure_db_initialized() -> None:
    """Ensure database is initialized."""
    from core.db import db
    from core.config import get_settings
    
    if not db.is_initialized:
        db.initialize(get_settings().database_url)


def discover_issues(
    user_id: int,
    labels: Optional[List[str]] = None,
    language: Optional[str] = None,
    min_stars: Optional[int] = None,
    limit: int = 100,
    apply_quality_filters: bool = True,
) -> List[Dict]:
    """
    Discover and store GitHub issues for a user.
    
    Args:
        user_id: User ID to associate issues with (required)
        labels: List of labels to search for
        language: Programming language filter
        min_stars: Minimum repository stars
        limit: Maximum number of issues to fetch
        apply_quality_filters: Apply default quality filters
        
    Returns:
        List of discovered issue dictionaries with id, title, url
    """
    _ensure_db_initialized()
    
    issues = search_issues(
        labels=labels,
        language=language,
        min_stars=min_stars,
        limit=limit,
        apply_quality_filters=apply_quality_filters
    )
    
    stored_issues = []
    
    from core.db import db
    from core.repositories import IssueRepository
    
    with db.session() as session:
        repo = IssueRepository(session)
        
        for issue in issues:
            try:
                # Extract repo info
                repo_url = issue.get("repository_url", "")
                repo_owner, repo_name = None, None
                if repo_url:
                    parts = repo_url.replace("https://api.github.com/repos/", "").split("/")
                    if len(parts) >= 2:
                        repo_owner, repo_name = parts[0], parts[1]
                
                # Get repo metadata
                repo_metadata = None
                if repo_owner and repo_name:
                    repo_metadata = get_repo_metadata_from_api(repo_owner, repo_name, use_cache=True)
                
                # Parse issue
                parsed = parse_issue(issue, repo_metadata)
                if not parsed:
                    continue
                
                # Analyze for technologies
                issue_body = parsed.get("body", "") or ""
                _, technologies, _ = analyze_job_text(issue_body)
                
                # Store using repository
                issue_data = {
                    "title": parsed.get("title", ""),
                    "url": parsed.get("url", ""),
                    "body": parsed.get("body"),
                    "repo_owner": parsed.get("repo_owner"),
                    "repo_name": parsed.get("repo_name"),
                    "repo_url": parsed.get("repo_url"),
                    "difficulty": parsed.get("difficulty"),
                    "issue_type": parsed.get("issue_type"),
                    "time_estimate": parsed.get("time_estimate"),
                    "labels": parsed.get("labels", []),
                    "repo_stars": parsed.get("repo_stars"),
                    "repo_forks": parsed.get("repo_forks"),
                    "repo_languages": parsed.get("repo_languages"),
                    "repo_topics": parsed.get("repo_topics"),
                    "last_commit_date": parsed.get("last_commit_date"),
                    "contributor_count": parsed.get("contributor_count"),
                    "is_active": parsed.get("is_active", True),
                    "technologies": technologies,
                }
                
                results = repo.bulk_upsert(user_id, [issue_data])
                if results:
                    stored_issues.append({
                        'id': results[0].id,
                        'title': parsed.get("title", ""),
                        'url': parsed.get("url", ""),
                    })
            except Exception:
                continue
    
    return stored_issues


def score_issue(issue_id: int, user_id: int, profile_path: Optional[str] = None) -> Dict:
    """
    Score a specific issue against the developer profile.
    
    Args:
        issue_id: ID of the issue to score
        user_id: User ID who owns the issue
        profile_path: Optional path to profile file
        
    Returns:
        Dictionary with score and breakdown
    """
    _ensure_db_initialized()
    
    profile = load_dev_profile(profile_path)
    
    from core.db import db
    from core.repositories import IssueRepository
    
    with db.session() as session:
        repo = IssueRepository(session)
        issue = repo.get_by_id(issue_id, user_id)
        
        if not issue:
            raise ValueError(f"Issue with ID {issue_id} not found for user {user_id}")
        
        return score_issue_against_profile(profile, issue.to_dict())


def score_all_issues(user_id: int, limit: Optional[int] = None, profile_path: Optional[str] = None) -> List[Dict]:
    """
    Score all issues for a user against the developer profile.
    
    Returns:
        List of scored issues sorted by score (descending)
    """
    _ensure_db_initialized()
    profile = load_dev_profile(profile_path)
    return score_profile_against_all_issues(profile=profile, limit=limit)


def get_top_matches_api(user_id: int, limit: int = 10, profile_path: Optional[str] = None) -> List[Dict]:
    """Get top N matching issues for the developer profile."""
    _ensure_db_initialized()
    profile = load_dev_profile(profile_path)
    return get_top_matches(profile=profile, limit=limit)


def train_model_api(
    force: bool = False,
    use_advanced: bool = True,
    use_stacking: bool = True,
    use_tuning: bool = True,
    tune_iterations: int = 50,
    legacy: bool = False,
) -> Dict:
    """
    Train the ML model.
    
    Returns:
        Dictionary with training metrics
    """
    _ensure_db_initialized()
    return train_ml_model(
        force=force,
        use_advanced=use_advanced,
        use_stacking=use_stacking,
        use_tuning=use_tuning,
        tune_iterations=tune_iterations,
        legacy=legacy
    )


def list_issues(
    user_id: int,
    difficulty: Optional[str] = None,
    issue_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict]:
    """
    List issues for a user with optional filters.
    
    Args:
        user_id: User ID (required)
        difficulty: Filter by difficulty level
        issue_type: Filter by issue type
        is_active: Filter by active status
        limit: Maximum number of results
        offset: Pagination offset
        
    Returns:
        List of issue dictionaries
    """
    _ensure_db_initialized()
    
    from core.db import db
    from core.repositories import IssueRepository
    
    with db.session() as session:
        repo = IssueRepository(session)
        
        filters = {}
        if difficulty:
            filters["difficulty"] = difficulty
        if issue_type:
            filters["issue_type"] = issue_type
        if is_active is not None:
            filters["is_active"] = is_active
        
        issues, total, _ = repo.list_with_bookmarks(user_id, filters, offset, limit)
        
        return [issue.to_dict() for issue in issues]


def get_profile(profile_path: Optional[str] = None) -> Dict:
    """Load developer profile."""
    return load_dev_profile(profile_path)


def save_profile(profile: Dict, profile_path: Optional[str] = None) -> None:
    """Save developer profile."""
    save_dev_profile(profile, profile_path)
