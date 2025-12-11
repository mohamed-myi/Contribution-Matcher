"""
Issue service - bridges FastAPI endpoints with core business logic.

Uses IssueRepository for database access.
"""

import contextlib

from sqlalchemy.orm import Session

from core import parsing

# Import modules (not functions) to allow test patching
from core.api import github_api
from core.logging import get_logger
from core.parsing import skill_extractor
from core.repositories import IssueRepository, ProfileRepository

from ..models import Issue, IssueBookmark, User
from ..schemas import IssueDiscoverRequest

logger = get_logger("api.issue_service")

# Labels appropriate for each experience level
EXPERIENCE_LEVEL_LABELS = {
    "beginner": ["good first issue", "good-first-issue", "beginner-friendly", "beginner", "easy"],
    "intermediate": [
        "help wanted",
        "help-wanted",
        "intermediate",
        "medium",
        "enhancement",
        "feature",
    ],
    "advanced": ["help wanted", "complex", "hard", "advanced", "architecture", "performance"],
    "expert": ["help wanted", "complex", "hard", "advanced", "critical", "security", "core"],
}

# Min stars appropriate for each experience level
EXPERIENCE_LEVEL_MIN_STARS = {
    "beginner": 50,
    "intermediate": 100,
    "advanced": 500,
    "expert": 1000,
}


def discover_issues_for_user(db: Session, user: User, request: IssueDiscoverRequest) -> list[Issue]:
    """
    Discover issues from GitHub and store them for the user.

    Uses experience level from user's profile to adjust search parameters.

    Args:
        db: Database session.
        user: Authenticated user requesting discovery.
        request: Discovery parameters including labels, language, and limit.

    Returns:
        List of stored Issue ORM instances.
    """
    # Get experience level from profile
    profile_repo = ProfileRepository(db)
    profile = profile_repo.get_by_user_id(user.id)
    experience_level = profile.experience_level if profile else "beginner"

    # Determine labels and min_stars based on experience
    level = experience_level.lower() if experience_level else "beginner"
    labels = request.labels or EXPERIENCE_LEVEL_LABELS.get(
        level, EXPERIENCE_LEVEL_LABELS["beginner"]
    )
    min_stars = (
        request.min_stars
        if request.min_stars is not None
        else EXPERIENCE_LEVEL_MIN_STARS.get(level, 10)
    )

    logger.info(
        "discovering_issues", experience_level=level, labels=labels[:3], min_stars=min_stars
    )

    # Search GitHub (use module.function for test patching)
    github_issues = github_api.search_issues(
        labels=labels,
        language=request.language,
        min_stars=min_stars,
        limit=request.limit,
        apply_quality_filters=request.apply_quality_filters,
    )

    # Parse and prepare issues for bulk upsert
    issues_data = []
    for issue in github_issues:
        # Extract repo info
        repo_owner, repo_name = None, None
        repo_url = issue.get("repository_url", "")
        if repo_url and repo_url.startswith("https://api.github.com/repos/"):
            parts = repo_url.replace("https://api.github.com/repos/", "").split("/")
            if len(parts) >= 2:
                repo_owner, repo_name = parts[0], parts[1]

        # Get repo metadata
        repo_metadata = None
        if repo_owner and repo_name:
            repo_metadata = github_api.get_repo_metadata_from_api(
                repo_owner, repo_name, use_cache=True
            )

        # Parse issue
        parsed = parsing.parse_issue(issue, repo_metadata)
        if not parsed:
            continue

        # Extract technologies
        technologies = []
        body = parsed.get("body") or ""
        if body:
            _, tech_list, _ = skill_extractor.analyze_job_text(body)
            technologies = tech_list

        issues_data.append(
            {
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
                "repo_topics": parsed.get("repo_topics") or [],
                "last_commit_date": parsed.get("last_commit_date"),
                "contributor_count": parsed.get("contributor_count"),
                "is_active": parsed.get("is_active", True),
                "technologies": technologies,
            }
        )

    # Bulk upsert using repository
    issue_repo = IssueRepository(db)
    stored_issues = issue_repo.bulk_upsert(user.id, issues_data)

    return stored_issues


def get_issue(db: Session, user: User, issue_id: int) -> Issue:
    """Get a single issue by ID, raising 404 if not found."""
    from fastapi import HTTPException, status

    repo = IssueRepository(db)
    issue = repo.get_by_id(issue_id, user.id)

    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return issue


def bookmark_issue(db: Session, user: User, issue_id: int) -> IssueBookmark:
    """Bookmark an issue."""
    issue = get_issue(db, user, issue_id)

    bookmark = (
        db.query(IssueBookmark)
        .filter(IssueBookmark.user_id == user.id, IssueBookmark.issue_id == issue.id)
        .first()
    )

    if not bookmark:
        bookmark = IssueBookmark(user_id=user.id, issue_id=issue.id)
        db.add(bookmark)
        db.commit()
        db.refresh(bookmark)

    return bookmark


def remove_bookmark(db: Session, user: User, issue_id: int) -> None:
    """Remove bookmark from an issue."""
    bookmark = (
        db.query(IssueBookmark)
        .filter(IssueBookmark.user_id == user.id, IssueBookmark.issue_id == issue_id)
        .first()
    )

    if bookmark:
        db.delete(bookmark)
        db.commit()


def get_bookmarks(db: Session, user: User) -> list[Issue]:
    """Get all bookmarked issues for a user."""
    return (
        db.query(Issue)
        .join(IssueBookmark, IssueBookmark.issue_id == Issue.id)
        .filter(
            IssueBookmark.user_id == user.id,
            Issue.is_active,
        )
        .order_by(IssueBookmark.created_at.desc())
        .all()
    )


def issue_to_dict(issue: Issue, is_bookmarked: bool = False) -> dict:
    """
    Convert an Issue model to a response dictionary.

    Handles issue_number extraction and description truncation.
    """
    # Extract issue_number from URL
    issue_number = None
    if issue.url:
        with contextlib.suppress(ValueError, IndexError):
            issue_number = int(issue.url.rstrip("/").split("/")[-1])

    # Truncate description
    description = None
    if issue.body:
        description = issue.body[:300] + ("..." if len(issue.body) > 300 else "")

    return {
        "id": issue.id,
        "title": issue.title,
        "url": issue.url,
        "difficulty": issue.difficulty,
        "issue_type": issue.issue_type,
        "repo_owner": issue.repo_owner,
        "repo_name": issue.repo_name,
        "repo_stars": issue.repo_stars,
        "repo_languages": issue.repo_languages,
        "issue_number": issue_number,
        "description": description,
        "technologies": [t.technology for t in issue.technologies] if issue.technologies else [],
        "labels": issue.labels or [],
        "repo_topics": issue.repo_topics or [],
        "created_at": issue.created_at,
        "is_bookmarked": is_bookmarked,
        "score": issue.cached_score,
        # Staleness fields
        "last_verified_at": issue.last_verified_at,
        "closed_at": issue.closed_at,
        "close_reason": issue.close_reason,
        "github_state": issue.github_state,
        "is_stale": issue.is_stale,
        "is_very_stale": issue.is_very_stale,
    }


def issue_to_detail_dict(issue: Issue, is_bookmarked: bool = False) -> dict:
    """Convert Issue model to detailed response dictionary."""
    base = issue_to_dict(issue, is_bookmarked)
    base.update(
        {
            "body": issue.body,
            "repo_url": issue.repo_url,
            "repo_forks": issue.repo_forks,
            "time_estimate": issue.time_estimate,
            "contributor_count": issue.contributor_count,
            "is_active": issue.is_active if issue.is_active is not None else True,
        }
    )
    return base


def issue_to_response_dict(issue: Issue, user_id: int, db: Session) -> dict:
    """
    Legacy compatibility function for scoring_service.

    Checks bookmark status via DB query. Prefer issue_to_dict() for new code.
    Use batch_issue_to_dict() for multiple issues to avoid N+1 queries.
    """
    is_bookmarked = (
        db.query(IssueBookmark)
        .filter(IssueBookmark.user_id == user_id, IssueBookmark.issue_id == issue.id)
        .first()
        is not None
    )

    return issue_to_dict(issue, is_bookmarked)


def batch_issue_to_dict(issues: list[Issue], bookmarked_ids: set) -> list[dict]:
    """
    Convert multiple issues to response dicts efficiently.

    Uses pre-fetched bookmark IDs to avoid N+1 queries.

    Args:
        issues: List of Issue models
        bookmarked_ids: Set of bookmarked issue IDs (from IssueRepository.list_with_bookmarks)

    Returns:
        List of issue response dictionaries
    """
    return [issue_to_dict(issue, issue.id in bookmarked_ids) for issue in issues]
