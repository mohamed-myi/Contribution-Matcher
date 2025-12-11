from datetime import datetime

from backend.app.models import DevProfile, Issue, IssueTechnology


def _seed_profile(session, user_id: int):
    session.add(
        DevProfile(
            user_id=user_id,
            skills=["python", "react"],
            experience_level="intermediate",
            interests=["web", "automation"],
            preferred_languages=["python"],
            time_availability_hours_per_week=10,
        )
    )
    session.commit()


def test_top_matches_returns_scores(authorized_client):
    client, _, session_factory = authorized_client
    session = session_factory()
    _seed_profile(session, user_id=1)

    issue = Issue(
        user_id=1,
        title="Fix bug",
        url="https://example.com/issues/1",
        difficulty="beginner",
        issue_type="bug",
        repo_owner="foo",
        repo_name="bar",
        repo_topics=["web"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        repo_stars=50,
        repo_forks=5,
        contributor_count=10,
    )
    session.add(issue)
    session.flush()
    session.add(IssueTechnology(issue_id=issue.id, technology="python"))
    session.commit()
    session.close()

    resp = client.get("/api/v1/scoring/top-matches", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "issues" in data
    assert len(data["issues"]) == 1
    assert data["issues"][0]["score"] > 0
    assert data["issues"][0]["title"] == "Fix bug"


def test_score_single_issue(authorized_client):
    client, _, session_factory = authorized_client
    session = session_factory()
    _seed_profile(session, user_id=1)

    issue = Issue(
        user_id=1,
        title="Add feature",
        url="https://example.com/issues/2",
        difficulty="intermediate",
        issue_type="feature",
        repo_owner="foo",
        repo_name="baz",
        repo_topics=["automation"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(issue)
    session.flush()
    session.add(IssueTechnology(issue_id=issue.id, technology="react"))
    issue_id = issue.id
    session.commit()
    session.close()

    resp = client.get(f"/api/v1/scoring/{issue_id}", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["issue_id"] == issue_id
    assert "breakdown" in body
    assert body["total_score"] >= 0
