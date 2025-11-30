"""
Issue service functions bridging FastAPI and core contribution matcher logic.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.api.github_api import search_issues, get_repo_metadata_from_api
from core.parsing import parse_issue
from core.parsing.skill_extractor import analyze_job_text
from core.logging import get_logger

from ..models import Issue, IssueBookmark, IssueTechnology, User, DevProfile
from ..schemas import IssueDiscoverRequest, IssueFilterParams

logger = get_logger("api.issue_service")


# Labels appropriate for each experience level
EXPERIENCE_LEVEL_LABELS = {
    "beginner": ["good first issue", "good-first-issue", "beginner-friendly", "beginner", "easy"],
    "intermediate": ["help wanted", "help-wanted", "intermediate", "medium", "enhancement", "feature"],
    "advanced": ["help wanted", "complex", "hard", "advanced", "architecture", "performance"],
    "expert": ["help wanted", "complex", "hard", "advanced", "critical", "security", "core"],
}

# Min stars appropriate for each experience level (higher level = more complex repos)
EXPERIENCE_LEVEL_MIN_STARS = {
    "beginner": 50,      # Well-maintained, documented repos
    "intermediate": 100, # More established projects
    "advanced": 500,     # Larger, more complex projects
    "expert": 1000,      # Major projects
}


def _get_labels_for_experience_level(experience_level: str, requested_labels: Optional[List[str]] = None) -> List[str]:
    """Get appropriate labels based on user's experience level."""
    if requested_labels:
        return requested_labels
    
    level = experience_level.lower() if experience_level else "beginner"
    return EXPERIENCE_LEVEL_LABELS.get(level, EXPERIENCE_LEVEL_LABELS["beginner"])


def _get_min_stars_for_experience_level(experience_level: str, requested_min_stars: Optional[int] = None) -> int:
    """Get appropriate min stars based on user's experience level."""
    if requested_min_stars is not None:
        return requested_min_stars
    
    level = experience_level.lower() if experience_level else "beginner"
    return EXPERIENCE_LEVEL_MIN_STARS.get(level, 10)


def discover_issues_for_user(
    db: Session,
    user: User,
    request: IssueDiscoverRequest,
) -> List[Issue]:
    # Get user's profile to determine experience level
    profile = db.query(DevProfile).filter(DevProfile.user_id == user.id).first()
    experience_level = profile.experience_level if profile else "beginner"
    
    # Use experience-appropriate labels if not specified
    labels = _get_labels_for_experience_level(experience_level, request.labels)
    min_stars = _get_min_stars_for_experience_level(experience_level, request.min_stars)
    
    logger.info(
        "discovering_issues",
        experience_level=experience_level,
        labels=labels,
        min_stars=min_stars,
    )
    
    github_issues = search_issues(
        labels=labels,
        language=request.language,
        min_stars=min_stars,
        limit=request.limit,
        apply_quality_filters=request.apply_quality_filters,
    )

    stored_issues: List[Issue] = []
    for issue in github_issues:
        repo_owner = None
        repo_name = None
        repo_url = issue.get("repository_url", "")
        if repo_url and repo_url.startswith("https://api.github.com/repos/"):
            parts = repo_url.replace("https://api.github.com/repos/", "").split("/")
            if len(parts) >= 2:
                repo_owner, repo_name = parts[0], parts[1]

        repo_metadata = None
        if repo_owner and repo_name:
            repo_metadata = get_repo_metadata_from_api(repo_owner, repo_name, use_cache=True)

        parsed = parse_issue(issue, repo_metadata)
        technologies = []
        body = parsed.get("body") or ""
        if body:
            _, technologies_extracted, _ = analyze_job_text(body)
            technologies = [(tech, category) for tech, category in technologies_extracted]

        db_issue = _upsert_issue(db, user.id, parsed)
        _replace_issue_technologies(db, db_issue, technologies)
        stored_issues.append(db_issue)

    return stored_issues


def _upsert_issue(db: Session, user_id: int, parsed_issue: dict) -> Issue:
    db_issue = (
        db.query(Issue)
        .filter(Issue.user_id == user_id, Issue.url == parsed_issue.get("url"))
        .one_or_none()
    )
    if not db_issue:
        db_issue = Issue(user_id=user_id, url=parsed_issue.get("url"))
        db.add(db_issue)

    db_issue.title = parsed_issue.get("title")
    db_issue.body = parsed_issue.get("body")
    db_issue.repo_owner = parsed_issue.get("repo_owner")
    db_issue.repo_name = parsed_issue.get("repo_name")
    db_issue.repo_url = parsed_issue.get("repo_url")
    db_issue.difficulty = parsed_issue.get("difficulty")
    db_issue.issue_type = parsed_issue.get("issue_type")
    db_issue.time_estimate = parsed_issue.get("time_estimate")
    db_issue.labels = parsed_issue.get("labels") or []
    db_issue.repo_stars = parsed_issue.get("repo_stars")
    db_issue.repo_forks = parsed_issue.get("repo_forks")
    db_issue.repo_languages = parsed_issue.get("repo_languages")
    db_issue.repo_topics = parsed_issue.get("repo_topics") or []
    db_issue.last_commit_date = parsed_issue.get("last_commit_date")
    db_issue.contributor_count = parsed_issue.get("contributor_count")
    db_issue.is_active = parsed_issue.get("is_active") if parsed_issue.get("is_active") is not None else True

    db.commit()
    db.refresh(db_issue)
    return db_issue


def _replace_issue_technologies(
    db: Session,
    issue: Issue,
    technologies: List[tuple[str, Optional[str]]],
) -> None:
    db.query(IssueTechnology).filter(IssueTechnology.issue_id == issue.id).delete()
    for tech_name, tech_category in technologies:
        db.add(
            IssueTechnology(
                issue_id=issue.id,
                technology=tech_name,
                technology_category=tech_category,
            )
        )
    db.commit()


def list_issues(
    db: Session,
    user: User,
    filters: IssueFilterParams,
) -> List[Issue]:
    query = db.query(Issue).filter(Issue.user_id == user.id)

    if filters.difficulty:
        query = query.filter(Issue.difficulty == filters.difficulty)
    if filters.technology:
        query = query.join(Issue.technologies).filter(
            IssueTechnology.technology == filters.technology
        )
    if filters.language:
        # Filter by language in repo_languages JSON field
        query = query.filter(Issue.repo_languages.contains(filters.language))
    if filters.repo_owner:
        query = query.filter(Issue.repo_owner == filters.repo_owner)
    if filters.issue_type:
        query = query.filter(Issue.issue_type == filters.issue_type)
    if filters.days_back:
        cutoff = datetime.utcnow() - timedelta(days=filters.days_back)
        query = query.filter(Issue.created_at >= cutoff)

    issues = (
        query.order_by(Issue.created_at.desc())
        .offset(filters.offset)
        .limit(filters.limit)
        .all()
    )
    return issues


def get_issue(
    db: Session,
    user: User,
    issue_id: int,
) -> Issue:
    issue = (
        db.query(Issue)
        .filter(Issue.user_id == user.id, Issue.id == issue_id)
        .one_or_none()
    )
    if not issue:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return issue


def bookmark_issue(db: Session, user: User, issue_id: int) -> IssueBookmark:
    issue = get_issue(db, user, issue_id)
    bookmark = (
        db.query(IssueBookmark)
        .filter(IssueBookmark.user_id == user.id, IssueBookmark.issue_id == issue.id)
        .one_or_none()
    )
    if not bookmark:
        bookmark = IssueBookmark(user_id=user.id, issue_id=issue.id)
        db.add(bookmark)
        db.commit()
        db.refresh(bookmark)
    return bookmark


def remove_bookmark(db: Session, user: User, issue_id: int) -> None:
    bookmark = (
        db.query(IssueBookmark)
        .filter(IssueBookmark.user_id == user.id, IssueBookmark.issue_id == issue_id)
        .one_or_none()
    )
    if bookmark:
        db.delete(bookmark)
        db.commit()


def get_bookmarks(db: Session, user: User) -> List[Issue]:
    bookmarks = (
        db.query(Issue)
        .join(IssueBookmark, IssueBookmark.issue_id == Issue.id)
        .filter(IssueBookmark.user_id == user.id)
        .order_by(IssueBookmark.created_at.desc())
        .all()
    )
    return bookmarks


def get_issue_stats(db: Session, user: User) -> dict:
    total = db.query(func.count(Issue.id)).filter(Issue.user_id == user.id).scalar() or 0
    by_difficulty = (
        db.query(Issue.difficulty, func.count(Issue.id))
        .filter(Issue.user_id == user.id)
        .group_by(Issue.difficulty)
        .all()
    )
    bookmarks = (
        db.query(func.count(IssueBookmark.id))
        .filter(IssueBookmark.user_id == user.id)
        .scalar()
        or 0
    )

    return {
        "total": total,
        "bookmarks": bookmarks,
        "by_difficulty": {difficulty or "unknown": count for difficulty, count in by_difficulty},
    }


def issue_to_response_dict(issue: Issue, user_id: int, db: Session) -> dict:
    """
    Convert an Issue ORM object to a dict suitable for IssueResponse serialization.
    Includes bookmark status check.
    """
    is_bookmarked = db.query(IssueBookmark).filter(
        IssueBookmark.user_id == user_id,
        IssueBookmark.issue_id == issue.id
    ).first() is not None
    
    # Extract issue_number from URL if not stored directly
    issue_number = getattr(issue, 'issue_number', None)
    if issue_number is None and issue.url:
        try:
            issue_number = int(issue.url.rstrip('/').split('/')[-1])
        except (ValueError, IndexError):
            issue_number = None
    
    # Get description from body (truncated)
    description = None
    if issue.body:
        description = issue.body[:300] + ('...' if len(issue.body) > 300 else '')
    
    return {
        "id": issue.id,
        "title": issue.title,
        "url": issue.url,
        "difficulty": issue.difficulty,
        "issue_type": issue.issue_type,
        "repo_owner": issue.repo_owner,
        "repo_name": issue.repo_name,
        "repo_stars": issue.repo_stars,
        "issue_number": issue_number,
        "description": description,
        "technologies": [tech.technology for tech in issue.technologies] if issue.technologies else [],
        "labels": issue.labels or [],
        "repo_topics": issue.repo_topics or [],
        "created_at": issue.created_at,
        "is_bookmarked": is_bookmarked,
        "score": getattr(issue, 'score', None),
    }


def serialize_issue(issue: Issue) -> dict:
    """
    Convert an Issue ORM object to a full dict (for CLI/legacy use).
    Does not include bookmark status.
    """
    # Extract issue_number from URL if not stored directly
    issue_number = getattr(issue, 'issue_number', None)
    if issue_number is None and issue.url:
        try:
            issue_number = int(issue.url.rstrip('/').split('/')[-1])
        except (ValueError, IndexError):
            issue_number = None
    
    # Get description from body (truncated)
    description = None
    if issue.body:
        description = issue.body[:300] + ('...' if len(issue.body) > 300 else '')
    
    return {
        "id": issue.id,
        "title": issue.title,
        "url": issue.url,
        "difficulty": issue.difficulty,
        "issue_type": issue.issue_type,
        "repo_owner": issue.repo_owner,
        "repo_name": issue.repo_name,
        "issue_number": issue_number,
        "description": description,
        "technologies": [tech.technology for tech in issue.technologies] if issue.technologies else [],
        "labels": issue.labels or [],
        "repo_topics": issue.repo_topics or [],
        "created_at": issue.created_at,
        "body": issue.body,
        "repo_url": issue.repo_url,
        "repo_stars": issue.repo_stars,
        "repo_forks": issue.repo_forks,
        "time_estimate": issue.time_estimate,
        "contributor_count": issue.contributor_count,
        "is_active": issue.is_active,
    }

