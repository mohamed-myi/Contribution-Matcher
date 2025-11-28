"""
Pytest fixtures for Contribution Matcher tests.
"""
import json
import os
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List
from unittest.mock import patch

import pytest

# Set test database path before importing database module
os.environ["CONTRIBUTION_MATCHER_DB_PATH"] = "test_contribution_matcher.db"

from contribution_matcher.database import init_db, upsert_issue, replace_issue_technologies, update_issue_label, upsert_repo_metadata
from contribution_matcher.profile import save_dev_profile


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh test database for each test."""
    # Remove test database if it exists
    test_db_path = "test_contribution_matcher.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    
    # Initialize fresh database
    init_db()
    
    yield test_db_path
    
    # Cleanup after test
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


@pytest.fixture
def sample_profile():
    """Sample developer profile for testing."""
    return {
        "skills": ["python", "javascript", "react", "django", "postgresql"],
        "experience_level": "intermediate",
        "interests": ["web development", "open source", "machine learning"],
        "preferred_languages": ["python", "javascript"],
        "time_availability_hours_per_week": 10,
    }


@pytest.fixture
def sample_github_issue():
    """Sample GitHub API issue response."""
    return {
        "id": 12345,
        "title": "Fix bug in authentication module",
        "body": "There's a bug in the authentication module that needs fixing. Should take about 2-3 hours.",
        "html_url": "https://github.com/testowner/testrepo/issues/123",
        "url": "https://api.github.com/repos/testowner/testrepo/issues/123",
        "repository_url": "https://api.github.com/repos/testowner/testrepo",
        "labels": [
            {"name": "bug"},
            {"name": "good first issue"},
            {"name": "python"}
        ],
        "state": "open",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-20T15:30:00Z",
    }


@pytest.fixture
def sample_repo_metadata():
    """Sample repository metadata."""
    return {
        "repo_owner": "testowner",
        "repo_name": "testrepo",
        "stars": 150,
        "forks": 25,
        "languages": {"Python": 50000, "JavaScript": 20000},
        "topics": ["web-development", "python", "django"],
        "last_commit_date": "2024-01-18T12:00:00Z",
        "contributor_count": 8,
    }


@pytest.fixture
def sample_parsed_issue():
    """Sample parsed issue data (as stored in database)."""
    return {
        "id": 1,
        "title": "Fix bug in authentication module",
        "url": "https://github.com/testowner/testrepo/issues/123",
        "body": "There's a bug in the authentication module that needs fixing. Should take about 2-3 hours.",
        "repo_owner": "testowner",
        "repo_name": "testrepo",
        "repo_url": "https://github.com/testowner/testrepo",
        "difficulty": "beginner",
        "issue_type": "bug",
        "time_estimate": "2-3 hours",
        "labels": json.dumps(["bug", "good first issue", "python"]),
        "repo_stars": 150,
        "repo_forks": 25,
        "repo_languages": json.dumps({"Python": 50000, "JavaScript": 20000}),
        "repo_topics": json.dumps(["web-development", "python", "django"]),
        "last_commit_date": "2024-01-18T12:00:00Z",
        "contributor_count": 8,
        "is_active": 1,
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-20T15:30:00Z",
        "label": None,
        "labeled_at": None,
    }


@pytest.fixture
def sample_issue_in_db(test_db, sample_parsed_issue):
    """Create a sample issue in the test database."""
    issue_id = upsert_issue(
        title=sample_parsed_issue["title"],
        url=sample_parsed_issue["url"],
        body=sample_parsed_issue["body"],
        repo_owner=sample_parsed_issue["repo_owner"],
        repo_name=sample_parsed_issue["repo_name"],
        repo_url=sample_parsed_issue["repo_url"],
        difficulty=sample_parsed_issue["difficulty"],
        issue_type=sample_parsed_issue["issue_type"],
        time_estimate=sample_parsed_issue["time_estimate"],
        labels=json.loads(sample_parsed_issue["labels"]),
        repo_stars=sample_parsed_issue["repo_stars"],
        repo_forks=sample_parsed_issue["repo_forks"],
        repo_languages=json.loads(sample_parsed_issue["repo_languages"]),
        repo_topics=json.loads(sample_parsed_issue["repo_topics"]),
        last_commit_date=sample_parsed_issue["last_commit_date"],
        contributor_count=sample_parsed_issue["contributor_count"],
        is_active=sample_parsed_issue["is_active"],
    )
    
    # Add technologies
    replace_issue_technologies(issue_id, [("python", "backend"), ("django", "backend")])
    
    return issue_id


@pytest.fixture
def multiple_issues_in_db(test_db):
    """Create multiple sample issues in the test database."""
    issues = [
        {
            "title": "Beginner Python bug fix",
            "url": "https://github.com/testowner/testrepo/issues/1",
            "body": "Easy bug fix for beginners. Takes about 1 hour.",
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "difficulty": "beginner",
            "issue_type": "bug",
            "time_estimate": "1 hour",
            "labels": ["bug", "good first issue"],
            "repo_stars": 100,
            "technologies": [("python", "backend")],
        },
        {
            "title": "Advanced feature implementation",
            "url": "https://github.com/testowner/testrepo/issues/2",
            "body": "Complex feature requiring deep knowledge. Weekend project.",
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "difficulty": "advanced",
            "issue_type": "feature",
            "time_estimate": "weekend project",
            "labels": ["feature", "advanced"],
            "repo_stars": 200,
            "technologies": [("python", "backend"), ("postgresql", "data")],
        },
        {
            "title": "Documentation update",
            "url": "https://github.com/testowner/testrepo/issues/3",
            "body": "Update README with new features.",
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "difficulty": "beginner",
            "issue_type": "documentation",
            "time_estimate": "quick task",
            "labels": ["documentation"],
            "repo_stars": 50,
            "technologies": [],
        },
    ]
    
    issue_ids = []
    for issue in issues:
        issue_id = upsert_issue(
            title=issue["title"],
            url=issue["url"],
            body=issue["body"],
            repo_owner=issue["repo_owner"],
            repo_name=issue["repo_name"],
            difficulty=issue["difficulty"],
            issue_type=issue["issue_type"],
            time_estimate=issue["time_estimate"],
            labels=issue["labels"],
            repo_stars=issue["repo_stars"],
        )
        if issue["technologies"]:
            replace_issue_technologies(issue_id, issue["technologies"])
        issue_ids.append(issue_id)
    
    return issue_ids


@pytest.fixture
def labeled_issues_for_ml(test_db, sample_profile):
    """Create labeled issues for ML training tests."""
    # Save profile first
    save_dev_profile(sample_profile)
    
    # Create issues with labels
    issues = [
        {
            "title": "Good match issue",
            "url": "https://github.com/testowner/testrepo/issues/10",
            "body": "Python Django bug fix. Should take 2 hours.",
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "difficulty": "intermediate",
            "issue_type": "bug",
            "time_estimate": "2 hours",
            "labels": ["bug", "python"],
            "repo_stars": 150,
            "technologies": [("python", "backend"), ("django", "backend")],
            "label": "good",
        },
        {
            "title": "Bad match issue",
            "url": "https://github.com/testowner/testrepo/issues/11",
            "body": "Complex C++ system programming. Requires expert knowledge.",
            "repo_owner": "testowner",
            "repo_name": "testrepo",
            "difficulty": "advanced",
            "issue_type": "feature",
            "time_estimate": "1 week",
            "labels": ["feature", "c++"],
            "repo_stars": 50,
            "technologies": [("c++", "backend")],
            "label": "bad",
        },
    ]
    
    issue_ids = []
    for issue in issues:
        issue_id = upsert_issue(
            title=issue["title"],
            url=issue["url"],
            body=issue["body"],
            repo_owner=issue["repo_owner"],
            repo_name=issue["repo_name"],
            difficulty=issue["difficulty"],
            issue_type=issue["issue_type"],
            time_estimate=issue["time_estimate"],
            labels=issue["labels"],
            repo_stars=issue["repo_stars"],
        )
        if issue["technologies"]:
            replace_issue_technologies(issue_id, issue["technologies"])
        update_issue_label(issue_id, issue["label"])
        issue_ids.append(issue_id)
    
    return issue_ids


@pytest.fixture
def mock_github_api():
    """Mock GitHub API responses."""
    with patch('github_api._make_request') as mock_request:
        yield mock_request


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for GitHub API calls."""
    with patch('requests.get') as mock_get:
        yield mock_get

