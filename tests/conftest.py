"""
Pytest fixtures for Contribution Matcher tests.

Uses ORM pattern with SQLAlchemy for database operations.
"""

import os
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.db import Base
from core.models import Issue, IssueTechnology
from core.profile import save_dev_profile


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh test database for each test using ORM."""
    # PostgreSQL configuration
    # Use environment variables or default to local Docker configuration
    # pytest-xdist sets PYTEST_XDIST_WORKER to values like "gw0", "gw1", etc.
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")

    postgres_user = os.environ.get("POSTGRES_USER", "postgres")
    postgres_password = os.environ.get("POSTGRES_PASSWORD", "postgres")
    postgres_db = os.environ.get("POSTGRES_DB", "contribution_matcher")
    postgres_host = os.environ.get("POSTGRES_HOST", "localhost")
    postgres_port = os.environ.get("POSTGRES_PORT", "5432")

    # Use a separate test database name to avoid wiping development data
    test_db_name = f"{postgres_db}_test_{worker_id or 'master'}"

    # Connect to default database to create the test database
    default_db_url = (
        f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/postgres"
    )

    # Create test database
    from sqlalchemy import text

    try:
        # Connect to 'postgres' database to create new DB
        admin_engine = create_engine(default_db_url, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            # Terminate existing connections to the test database
            conn.execute(
                text(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{test_db_name}'
                AND pid <> pg_backend_pid();
            """)
            )
            # Drop if exists
            conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name}"))
            # Create fresh
            conn.execute(text(f"CREATE DATABASE {test_db_name}"))
        admin_engine.dispose()
    except Exception as e:
        pytest.fail(f"Could not create test database: {e}")

    # Connect to the new test database
    db_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{test_db_name}"

    engine = create_engine(db_url)

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create session factory
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    yield db_url, TestingSessionLocal, engine

    # Cleanup
    engine.dispose()
    # Optional: Drop database after test run?
    # To keep debugging data, we might leave it.
    # But for clean state in local dev, we might want to drop it.
    # However, since we use DROP IF EXISTS at start, it cleans up next time.
    # Leaving it allows inspection.


@pytest.fixture
def test_session(test_db):
    """Get a test session from the test database."""
    _, TestingSessionLocal, _ = test_db
    session = TestingSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


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
        "labels": [{"name": "bug"}, {"name": "good first issue"}, {"name": "python"}],
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
        "title": "Fix bug in authentication module",
        "url": "https://github.com/testowner/testrepo/issues/123",
        "body": "There's a bug in the authentication module that needs fixing. Should take about 2-3 hours.",
        "repo_owner": "testowner",
        "repo_name": "testrepo",
        "repo_url": "https://github.com/testowner/testrepo",
        "difficulty": "beginner",
        "issue_type": "bug",
        "time_estimate": "2-3 hours",
        "labels": ["bug", "good first issue", "python"],
        "repo_stars": 150,
        "repo_forks": 25,
        "repo_languages": {"Python": 50000, "JavaScript": 20000},
        "repo_topics": ["web-development", "python", "django"],
        "last_commit_date": "2024-01-18T12:00:00Z",
        "contributor_count": 8,
        "is_active": True,
    }


def _create_test_user(session):
    """Helper to create a test user for issues."""
    from core.models import User

    user = User(
        github_id="test_user_123",
        github_username="testuser",
        email="test@example.com",
    )
    session.add(user)
    session.flush()
    return user


def _create_issue_with_technologies(session, user_id, issue_data, technologies=None):
    """Helper to create an issue with technologies using ORM."""
    issue = Issue(
        user_id=user_id,
        title=issue_data.get("title"),
        url=issue_data.get("url"),
        body=issue_data.get("body"),
        repo_owner=issue_data.get("repo_owner"),
        repo_name=issue_data.get("repo_name"),
        repo_url=issue_data.get("repo_url"),
        difficulty=issue_data.get("difficulty"),
        issue_type=issue_data.get("issue_type"),
        time_estimate=issue_data.get("time_estimate"),
        labels=issue_data.get("labels"),
        repo_stars=issue_data.get("repo_stars"),
        repo_forks=issue_data.get("repo_forks"),
        repo_languages=issue_data.get("repo_languages"),
        repo_topics=issue_data.get("repo_topics"),
        last_commit_date=issue_data.get("last_commit_date"),
        contributor_count=issue_data.get("contributor_count"),
        is_active=issue_data.get("is_active", True),
        label=issue_data.get("label"),
    )
    session.add(issue)
    session.flush()

    # Add technologies
    if technologies:
        for tech, category in technologies:
            tech_obj = IssueTechnology(
                issue_id=issue.id,
                technology=tech,
                technology_category=category,
            )
            session.add(tech_obj)
        session.flush()

    return issue


@pytest.fixture
def sample_issue_in_db(test_session, sample_parsed_issue):
    """Create a sample issue in the test database using ORM."""
    user = _create_test_user(test_session)
    issue = _create_issue_with_technologies(
        test_session,
        user.id,
        sample_parsed_issue,
        technologies=[("python", "backend"), ("django", "backend")],
    )
    test_session.commit()
    return issue.id, user.id


@pytest.fixture
def multiple_issues_in_db(test_session):
    """Create multiple sample issues in the test database using ORM."""
    user = _create_test_user(test_session)

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
    for issue_data in issues:
        technologies = issue_data.pop("technologies", [])
        issue = _create_issue_with_technologies(test_session, user.id, issue_data, technologies)
        issue_ids.append(issue.id)

    test_session.commit()
    return issue_ids, user.id


@pytest.fixture
def labeled_issues_for_ml(test_session, sample_profile):
    """Create labeled issues for ML training tests using ORM."""
    # Create user first
    user = _create_test_user(test_session)

    # Save profile
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
    for issue_data in issues:
        technologies = issue_data.pop("technologies", [])
        issue = _create_issue_with_technologies(test_session, user.id, issue_data, technologies)
        issue_ids.append(issue.id)

    test_session.commit()
    return issue_ids, user.id


@pytest.fixture
def mock_github_api():
    """Mock GitHub API responses."""
    with patch("github_api._make_request") as mock_request:
        yield mock_request


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for GitHub API calls."""
    with patch("requests.get") as mock_get:
        yield mock_get


@pytest.fixture
def init_test_db(test_db, monkeypatch):
    """Initialize the global db object with the test database URL."""
    db_url, _, _ = test_db
    # Set DATABASE_URL environment variable
    monkeypatch.setenv("DATABASE_URL", db_url)
    # Reset and re-initialize the global db object
    from core.db import db

    if db.is_initialized:
        db.engine.dispose()
    db._initialized = False
    db.initialize(db_url)
    # Create a user with id=1 for CLI functions that default to user_id=1
    from core.models import User

    with db.session() as session:
        # For Postgres, we need to handle ID sequence/conflict if we force ID=1
        # But User model usually uses string ID (github_id) or auto-increment integer ID
        # Let's check if user exists first
        existing_user = session.query(User).filter(User.id == 1).first()
        if not existing_user:
            user = User(
                github_id="test_user_1",
                github_username="testuser1",
                email="test1@example.com",
            )
            session.add(user)
            session.commit()
    yield db_url
    # Cleanup
    if db.is_initialized:
        db.engine.dispose()
    db._initialized = False
