"""
Comprehensive tests for issue filtering functionality.

Tests all filter types:
- difficulty
- issue_type
- language (JSON key extraction)
- min_stars
- score_range
- days_back
- technology
- Combined filters
"""

from datetime import datetime, timedelta, timezone

from backend.app.models import Issue
from core.models import IssueTechnology


def create_test_issues(session, user_id=1):
    """Create a diverse set of test issues with various attributes."""
    issues = [
        # Issue 1: Python, beginner, bug, 100 stars, score 85
        Issue(
            user_id=user_id,
            title="Fix Python logging bug",
            url="https://github.com/test/repo1/issues/1",
            difficulty="beginner",
            issue_type="bug",
            repo_owner="test",
            repo_name="repo1",
            repo_stars=100,
            repo_languages={"Python": 50000, "JavaScript": 10000},
            cached_score=85.0,
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
            is_active=True,
        ),
        # Issue 2: JavaScript, intermediate, feature, 500 stars, score 65
        Issue(
            user_id=user_id,
            title="Add new React component",
            url="https://github.com/test/repo2/issues/2",
            difficulty="intermediate",
            issue_type="feature",
            repo_owner="test",
            repo_name="repo2",
            repo_stars=500,
            repo_languages={"JavaScript": 80000, "TypeScript": 20000},
            cached_score=65.0,
            created_at=datetime.now(timezone.utc) - timedelta(days=15),
            is_active=True,
        ),
        # Issue 3: Go, advanced, enhancement, 1000 stars, score 45
        Issue(
            user_id=user_id,
            title="Optimize Go performance",
            url="https://github.com/test/repo3/issues/3",
            difficulty="advanced",
            issue_type="enhancement",
            repo_owner="test",
            repo_name="repo3",
            repo_stars=1000,
            repo_languages={"Go": 100000},
            cached_score=45.0,
            created_at=datetime.now(timezone.utc) - timedelta(days=45),
            is_active=True,
        ),
        # Issue 4: Python, beginner, documentation, 50 stars, score 90
        Issue(
            user_id=user_id,
            title="Improve Python docs",
            url="https://github.com/test/repo4/issues/4",
            difficulty="beginner",
            issue_type="documentation",
            repo_owner="test",
            repo_name="repo4",
            repo_stars=50,
            repo_languages={"Python": 30000},
            cached_score=90.0,
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
            is_active=True,
        ),
        # Issue 5: TypeScript, intermediate, bug, 2000 stars, score 75
        Issue(
            user_id=user_id,
            title="Fix TypeScript type error",
            url="https://github.com/test/repo5/issues/5",
            difficulty="intermediate",
            issue_type="bug",
            repo_owner="test",
            repo_name="repo5",
            repo_stars=2000,
            repo_languages={"TypeScript": 90000, "JavaScript": 5000},
            cached_score=75.0,
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
            is_active=True,
        ),
    ]

    session.add_all(issues)
    session.commit()

    # Add technologies
    technologies = [
        IssueTechnology(issue_id=1, technology="Python", technology_category="language"),
        IssueTechnology(issue_id=1, technology="logging", technology_category="library"),
        IssueTechnology(issue_id=2, technology="React", technology_category="framework"),
        IssueTechnology(issue_id=2, technology="JavaScript", technology_category="language"),
        IssueTechnology(issue_id=3, technology="Go", technology_category="language"),
        IssueTechnology(issue_id=3, technology="performance", technology_category="concept"),
        IssueTechnology(issue_id=4, technology="Python", technology_category="language"),
        IssueTechnology(issue_id=4, technology="documentation", technology_category="concept"),
        IssueTechnology(issue_id=5, technology="TypeScript", technology_category="language"),
    ]
    session.add_all(technologies)
    session.commit()

    return issues


class TestDifficultyFilter:
    """Tests for difficulty filter."""

    def test_filter_by_beginner(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"difficulty": "beginner"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for issue in data["issues"]:
            assert issue["difficulty"] == "beginner"

    def test_filter_by_intermediate(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"difficulty": "intermediate"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for issue in data["issues"]:
            assert issue["difficulty"] == "intermediate"

    def test_filter_by_advanced(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"difficulty": "advanced"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["issues"][0]["difficulty"] == "advanced"


class TestIssueTypeFilter:
    """Tests for issue_type filter."""

    def test_filter_by_bug(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"issue_type": "bug"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for issue in data["issues"]:
            assert issue["issue_type"] == "bug"

    def test_filter_by_feature(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"issue_type": "feature"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["issues"][0]["issue_type"] == "feature"

    def test_filter_by_documentation(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"issue_type": "documentation"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["issues"][0]["issue_type"] == "documentation"


class TestLanguageFilter:
    """Tests for language filter (JSON key extraction)."""

    def test_filter_by_python(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"language": "Python"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for issue in data["issues"]:
            assert "Python" in (issue.get("repo_languages") or {})

    def test_filter_by_javascript(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"language": "JavaScript"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Issue 1, 2 and 5 have JavaScript
        assert data["total"] == 3

    def test_filter_by_go(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"language": "Go"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert "Go" in data["issues"][0].get("repo_languages", {})

    def test_filter_by_nonexistent_language(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"language": "Rust"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


class TestMinStarsFilter:
    """Tests for min_stars filter."""

    def test_filter_min_stars_100(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"min_stars": 100},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4  # All except 50 stars
        for issue in data["issues"]:
            assert issue["repo_stars"] >= 100

    def test_filter_min_stars_500(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"min_stars": 500},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3  # 500, 1000, 2000
        for issue in data["issues"]:
            assert issue["repo_stars"] >= 500

    def test_filter_min_stars_1000(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"min_stars": 1000},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # 1000, 2000
        for issue in data["issues"]:
            assert issue["repo_stars"] >= 1000

    def test_filter_min_stars_too_high(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"min_stars": 10000},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


class TestScoreRangeFilter:
    """Tests for score_range filter."""

    def test_filter_score_high(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"score_range": "high"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # 85, 90
        for issue in data["issues"]:
            assert issue["score"] >= 80

    def test_filter_score_medium(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"score_range": "medium"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # 65, 75
        for issue in data["issues"]:
            assert 50 <= issue["score"] < 80

    def test_filter_score_low(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"score_range": "low"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1  # 45
        for issue in data["issues"]:
            assert issue["score"] < 50


class TestDaysBackFilter:
    """Tests for days_back filter."""

    def test_filter_last_7_days(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"days_back": 7},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # 3 days, 5 days

    def test_filter_last_14_days(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"days_back": 14},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3  # 3, 5, 10 days

    def test_filter_last_30_days(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"days_back": 30},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4  # All except 45 days


class TestTechnologyFilter:
    """Tests for technology filter."""

    def test_filter_by_python_tech(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"technology": "Python"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # Issues 1 and 4

    def test_filter_by_react(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"technology": "React"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    def test_filter_technology_case_insensitive(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        # Should match "React" with lowercase
        resp = client.get(
            "/api/v1/issues",
            params={"technology": "react"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1


class TestCombinedFilters:
    """Tests for combining multiple filters."""

    def test_difficulty_and_issue_type(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"difficulty": "beginner", "issue_type": "bug"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["issues"][0]["difficulty"] == "beginner"
        assert data["issues"][0]["issue_type"] == "bug"

    def test_language_and_min_stars(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"language": "JavaScript", "min_stars": 1000},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1  # Only issue 5 with 2000 stars

    def test_difficulty_score_and_days(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={
                "difficulty": "beginner",
                "score_range": "high",
                "days_back": 7,
            },
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Issue 1: beginner, score 85, 5 days old
        # Issue 4: beginner, score 90, 3 days old
        assert data["total"] == 2

    def test_all_filters_no_match(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={
                "difficulty": "advanced",
                "language": "Python",
                "min_stars": 10000,
            },
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


class TestPagination:
    """Tests for pagination with filters."""

    def test_pagination_with_filter(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        # Get first page
        resp = client.get(
            "/api/v1/issues",
            params={"limit": 2, "offset": 0},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["issues"]) == 2
        assert data["total"] == 5

        # Get second page
        resp = client.get(
            "/api/v1/issues",
            params={"limit": 2, "offset": 2},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["issues"]) == 2
        assert data["total"] == 5

    def test_pagination_with_difficulty_filter(self, authorized_client):
        client, _, session_factory = authorized_client
        session = session_factory()
        create_test_issues(session)
        session.close()

        resp = client.get(
            "/api/v1/issues",
            params={"difficulty": "beginner", "limit": 1, "offset": 0},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["issues"]) == 1
        assert data["total"] == 2

        resp = client.get(
            "/api/v1/issues",
            params={"difficulty": "beginner", "limit": 1, "offset": 1},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["issues"]) == 1
        assert data["total"] == 2
