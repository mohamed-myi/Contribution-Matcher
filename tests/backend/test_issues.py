from datetime import datetime

from backend.app.models import Issue
from backend.app.services import issue_service
from core.api import github_api
from core import parsing
from core.parsing import skill_extractor


def test_issue_discovery_persists_results(monkeypatch, authorized_client):
    client, override_current_user, session_factory = authorized_client

    fake_issue = {
        "title": "Test issue",
        "html_url": "https://github.com/foo/bar/issues/1",
        "repository_url": "https://api.github.com/repos/foo/bar",
        "body": "Need help with Python",
        "labels": [{"name": "good first issue"}],
    }

    # Patch at the source modules
    monkeypatch.setattr(
        github_api, "search_issues", lambda **kwargs: [fake_issue]
    )
    monkeypatch.setattr(
        github_api,
        "get_repo_metadata_from_api",
        lambda owner, name, use_cache=True: {"stars": 10, "forks": 1},
    )
    monkeypatch.setattr(
        parsing,
        "parse_issue",
        lambda issue, repo: {
            "title": issue["title"],
            "url": issue["html_url"],
            "body": issue["body"],
            "labels": ["good first issue"],
            "repo_owner": "foo",
            "repo_name": "bar",
            "repo_url": "https://github.com/foo/bar",
            "difficulty": "beginner",
            "issue_type": "bug",
            "time_estimate": "2h",
            "repo_stars": 10,
            "repo_forks": 1,
            "repo_languages": {"Python": 1000},
            "repo_topics": ["python"],
            "last_commit_date": "2023-01-01",
            "contributor_count": 5,
            "is_active": True,
        },
    )
    monkeypatch.setattr(
        skill_extractor,
        "analyze_job_text",
        lambda body: ("backend", [("python", "language")], {}),
    )

    resp = client.post(
        "/api/issues/discover",
        json={"labels": ["good first issue"], "limit": 1},
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "issues" in data
    assert len(data["issues"]) == 1
    assert data["issues"][0]["title"] == "Test issue"

    session = session_factory()
    from backend.app.models import Issue

    issues_count = session.query(Issue).count()
    assert issues_count == 1
    session.close()


def test_list_issues_filters_by_difficulty(monkeypatch, authorized_client):
    client, _, session_factory = authorized_client

    # Seed DB manually
    session = session_factory()
    session.add_all(
        [
            Issue(
                user_id=1,
                title="Easy task",
                url="https://example.com/1",
                difficulty="beginner",
                created_at=datetime.utcnow(),
            ),
            Issue(
                user_id=1,
                title="Hard task",
                url="https://example.com/2",
                difficulty="advanced",
                created_at=datetime.utcnow(),
            ),
        ]
    )
    session.commit()
    session.close()

    resp = client.get(
        "/api/issues",
        params={"difficulty": "beginner"},
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "issues" in data
    assert len(data["issues"]) == 1
    assert data["issues"][0]["title"] == "Easy task"
