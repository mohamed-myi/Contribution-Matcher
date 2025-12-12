from datetime import datetime, timezone

from backend.app.models import DevProfile, Issue, IssueTechnology


def _prepare_issues(session, user_id: int):
    issue_ids = []
    for idx in range(4):
        issue = Issue(
            user_id=user_id,
            title=f"Issue {idx}",
            url=f"https://example.com/issues/{idx}",
            difficulty="beginner" if idx % 2 == 0 else "advanced",
            issue_type="bug",
            repo_topics=["ml"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            repo_stars=10,
            repo_forks=1,
        )
        session.add(issue)
        session.flush()
        session.add(IssueTechnology(issue_id=issue.id, technology="python"))
        issue_ids.append(issue.id)
    session.commit()
    return issue_ids


def _ensure_profile(session, user_id: int):
    session.add(
        DevProfile(
            user_id=user_id,
            skills=["python"],
            experience_level="intermediate",
            interests=["ml"],
            preferred_languages=["python"],
            time_availability_hours_per_week=5,
        )
    )
    session.commit()


def test_label_and_status(authorized_client):
    client, _, session_factory = authorized_client
    session = session_factory()
    _ensure_profile(session, user_id=1)
    issues = _prepare_issues(session, user_id=1)
    session.close()

    resp = client.post(
        f"/api/v1/ml/label/{issues[0]}",
        json={"label": "good"},
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 200

    status_resp = client.get("/api/v1/ml/label-status", headers={"Authorization": "Bearer fake"})
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["good_count"] == 1
    assert data["labeled_count"] == 1


def test_label_rejects_invalid_label(authorized_client):
    client, _, session_factory = authorized_client
    session = session_factory()
    _ensure_profile(session, user_id=1)
    issues = _prepare_issues(session, user_id=1)
    session.close()

    resp = client.post(
        f"/api/v1/ml/label/{issues[0]}",
        json={"label": "junk"},
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert "detail" in body
    assert "Invalid label" in body["detail"]


def test_train_model(authorized_client, monkeypatch, tmp_path):
    client, _, session_factory = authorized_client
    session = session_factory()
    _ensure_profile(session, user_id=1)
    issues = _prepare_issues(session, user_id=1)
    session.close()

    for idx, issue_id in enumerate(issues):
        label = "good" if idx % 2 == 0 else "bad"
        client.post(
            f"/api/v1/ml/label/{issue_id}",
            json={"label": label},
            headers={"Authorization": "Bearer fake"},
        )

    monkeypatch.setenv("CONTRIBUTION_MATCHER_MODEL_DIR", str(tmp_path))

    resp = client.post(
        "/api/v1/ml/train",
        json={"test_size": 0.25},
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "metrics" in body
    assert body["model_type"] == "logistic_regression"
    assert body["metrics"]["samples"] >= 4

    info_resp = client.get("/api/v1/ml/model-info", headers={"Authorization": "Bearer fake"})
    assert info_resp.status_code == 200


def test_evaluate_model(authorized_client):
    client, _, session_factory = authorized_client
    session = session_factory()
    _ensure_profile(session, user_id=1)
    issues = _prepare_issues(session, user_id=1)
    session.close()

    for idx, issue_id in enumerate(issues):
        label = "good" if idx % 2 == 0 else "bad"
        client.post(
            f"/api/v1/ml/label/{issue_id}",
            json={"label": label},
            headers={"Authorization": "Bearer fake"},
        )

    resp = client.post(
        "/api/v1/ml/evaluate",
        json={"model_type": "logistic_regression"},
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_type"] == "logistic_regression"
    assert "accuracy" in data
