"""
CLI Database Helper Functions using ORM.

Provides ORM-based implementations of database operations for the CLI.
These replace the deprecated SQLite functions from core.database.database.
"""

import csv
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from core.db import db
from core.models import Issue, IssueTechnology, RepoMetadata


def init_database():
    """Initialize the database connection and create tables."""
    from core.config import get_settings
    settings = get_settings()
    if not db.is_initialized:
        db.initialize(settings.database_url)
    db.create_all_tables()


def upsert_issue(
    title: str,
    url: str,
    body: Optional[str] = None,
    repo_owner: Optional[str] = None,
    repo_name: Optional[str] = None,
    repo_url: Optional[str] = None,
    difficulty: Optional[str] = None,
    issue_type: Optional[str] = None,
    time_estimate: Optional[str] = None,
    labels: Optional[List[str]] = None,
    repo_stars: Optional[int] = None,
    repo_forks: Optional[int] = None,
    repo_languages: Optional[Dict[str, int]] = None,
    repo_topics: Optional[List[str]] = None,
    last_commit_date: Optional[str] = None,
    contributor_count: Optional[int] = None,
    is_active: bool = True,
    user_id: int = 1,  # Default CLI user
) -> int:
    """Insert or update an issue using ORM."""
    with db.session() as session:
        # Find existing issue by URL
        existing = session.query(Issue).filter(
            Issue.user_id == user_id,
            Issue.url == url,
        ).first()
        
        if existing:
            existing.title = title
            existing.body = body
            existing.repo_owner = repo_owner
            existing.repo_name = repo_name
            existing.repo_url = repo_url
            existing.difficulty = difficulty
            existing.issue_type = issue_type
            existing.time_estimate = time_estimate
            existing.labels = labels
            existing.repo_stars = repo_stars
            existing.repo_forks = repo_forks
            existing.repo_languages = repo_languages
            existing.repo_topics = repo_topics
            existing.last_commit_date = last_commit_date
            existing.contributor_count = contributor_count
            existing.is_active = is_active
            existing.updated_at = datetime.utcnow()
            session.flush()
            return existing.id
        else:
            issue = Issue(
                user_id=user_id,
                title=title,
                url=url,
                body=body,
                repo_owner=repo_owner,
                repo_name=repo_name,
                repo_url=repo_url,
                difficulty=difficulty,
                issue_type=issue_type,
                time_estimate=time_estimate,
                labels=labels,
                repo_stars=repo_stars,
                repo_forks=repo_forks,
                repo_languages=repo_languages,
                repo_topics=repo_topics,
                last_commit_date=last_commit_date,
                contributor_count=contributor_count,
                is_active=is_active,
            )
            session.add(issue)
            session.flush()
            return issue.id


def replace_issue_technologies(
    issue_id: int,
    technologies: List[Tuple[str, Optional[str]]],
) -> None:
    """Replace issue technologies for an issue using ORM."""
    with db.session() as session:
        # Clear existing
        session.query(IssueTechnology).filter(
            IssueTechnology.issue_id == issue_id
        ).delete()
        
        # Add new
        for tech, category in technologies:
            tech_obj = IssueTechnology(
                issue_id=issue_id,
                technology=tech,
                technology_category=category,
            )
            session.add(tech_obj)


def update_issue_label(issue_id: int, label: str) -> bool:
    """Update label for an issue using ORM."""
    if label not in ['good', 'bad']:
        return False
    
    with db.session() as session:
        issue = session.query(Issue).filter(Issue.id == issue_id).first()
        if issue:
            issue.label = label
            issue.labeled_at = datetime.utcnow()
            return True
        return False


def query_issues(
    difficulty: Optional[str] = None,
    issue_type: Optional[str] = None,
    label: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    user_id: int = 1,
) -> List[Dict]:
    """Query issues using ORM."""
    with db.session() as session:
        query = session.query(Issue).filter(Issue.user_id == user_id)
        
        if difficulty:
            query = query.filter(Issue.difficulty == difficulty)
        if issue_type:
            query = query.filter(Issue.issue_type == issue_type)
        if label:
            query = query.filter(Issue.label == label)
        if is_active is not None:
            query = query.filter(Issue.is_active == is_active)
        
        query = query.order_by(Issue.created_at.desc())
        query = query.offset(offset).limit(limit)
        
        return [issue.to_dict() for issue in query.all()]


def query_unlabeled_issues(limit: int = 100, user_id: int = 1) -> List[Dict]:
    """Query unlabeled issues using ORM."""
    with db.session() as session:
        issues = session.query(Issue).filter(
            Issue.user_id == user_id,
            Issue.label.is_(None),
            Issue.is_active == True,
        ).order_by(Issue.created_at.desc()).limit(limit).all()
        
        return [issue.to_dict() for issue in issues]


def get_issue_technologies(issue_id: int) -> List[Tuple[str, Optional[str]]]:
    """Get technologies for an issue using ORM."""
    with db.session() as session:
        techs = session.query(IssueTechnology).filter(
            IssueTechnology.issue_id == issue_id
        ).all()
        return [(t.technology, t.technology_category) for t in techs]


def get_all_issue_urls(user_id: int = 1) -> List[str]:
    """Get all active issue URLs using ORM."""
    with db.session() as session:
        results = session.query(Issue.url).filter(
            Issue.user_id == user_id,
            Issue.is_active == True,
            Issue.url.isnot(None),
        ).all()
        return [row[0] for row in results]


def mark_issues_inactive(urls: List[str]) -> int:
    """Mark issues as inactive by URL using ORM."""
    if not urls:
        return 0
    
    with db.session() as session:
        result = session.query(Issue).filter(
            Issue.url.in_(urls)
        ).update({"is_active": False}, synchronize_session=False)
        return result


def get_statistics(user_id: int = 1) -> Dict:
    """Get database statistics using ORM."""
    from sqlalchemy import func
    
    with db.session() as session:
        total_issues = session.query(func.count(Issue.id)).filter(
            Issue.user_id == user_id
        ).scalar()
        
        active_issues = session.query(func.count(Issue.id)).filter(
            Issue.user_id == user_id,
            Issue.is_active == True,
        ).scalar()
        
        labeled_issues = session.query(func.count(Issue.id)).filter(
            Issue.user_id == user_id,
            Issue.label.isnot(None),
        ).scalar()
        
        by_difficulty = dict(
            session.query(Issue.difficulty, func.count(Issue.id))
            .filter(Issue.user_id == user_id)
            .group_by(Issue.difficulty)
            .all()
        )
        
        return {
            "total_issues": total_issues,
            "active_issues": active_issues,
            "labeled_issues": labeled_issues,
            "by_difficulty": by_difficulty,
        }


def get_variety_statistics(user_id: int = 1) -> Dict:
    """Get variety statistics using ORM."""
    from sqlalchemy import func
    
    with db.session() as session:
        by_difficulty = dict(
            session.query(Issue.difficulty, func.count(Issue.id))
            .filter(Issue.user_id == user_id, Issue.is_active == True)
            .group_by(Issue.difficulty)
            .all()
        )
        
        by_type = dict(
            session.query(Issue.issue_type, func.count(Issue.id))
            .filter(Issue.user_id == user_id, Issue.is_active == True)
            .group_by(Issue.issue_type)
            .all()
        )
        
        top_repos = dict(
            session.query(Issue.repo_owner, func.count(Issue.id))
            .filter(Issue.user_id == user_id, Issue.is_active == True)
            .group_by(Issue.repo_owner)
            .order_by(func.count(Issue.id).desc())
            .limit(10)
            .all()
        )
        
        return {
            "by_difficulty": by_difficulty,
            "by_type": by_type,
            "top_repos": top_repos,
        }


def get_labeling_statistics(user_id: int = 1) -> Dict:
    """Get labeling statistics using ORM."""
    from sqlalchemy import func
    
    with db.session() as session:
        by_label = dict(
            session.query(Issue.label, func.count(Issue.id))
            .filter(Issue.user_id == user_id, Issue.label.isnot(None))
            .group_by(Issue.label)
            .all()
        )
        
        return {
            "total_labeled": sum(by_label.values()) if by_label else 0,
            "by_label": by_label,
        }


def export_to_csv(filepath: str, user_id: int = 1) -> int:
    """Export issues to CSV file using ORM."""
    issues = query_issues(is_active=True, limit=10000, user_id=user_id)
    
    if not issues:
        return 0
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=issues[0].keys())
        writer.writeheader()
        writer.writerows(issues)
    
    return len(issues)


def export_to_json(filepath: str, user_id: int = 1) -> int:
    """Export issues to JSON file using ORM."""
    issues = query_issues(is_active=True, limit=10000, user_id=user_id)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(issues, f, indent=2, default=str)
    
    return len(issues)
