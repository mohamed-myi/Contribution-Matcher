from backend.app.routers import jobs as jobs_router


def test_jobs_api_requires_authentication(test_app_client):
    """Test that jobs API requires authentication."""
    client, _ = test_app_client

    # All jobs endpoints should return 401 without authentication
    resp = client.get("/api/jobs")
    assert resp.status_code == 401

    resp = client.post("/api/jobs/run", json={"job_id": "test"})
    assert resp.status_code == 401

    resp = client.post("/api/jobs/reschedule", json={"job_id": "test", "cron": "* * * * *"})
    assert resp.status_code == 401


def test_jobs_api_disabled_returns_503(authorized_client):
    client, _, _ = authorized_client
    resp = client.get("/api/jobs", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Internal scheduler is disabled"


def _enable_scheduler(monkeypatch):
    class DummySettings:
        enable_scheduler = True

    monkeypatch.setattr(jobs_router, "get_settings", lambda: DummySettings())


def test_jobs_api_list(monkeypatch, authorized_client):
    _enable_scheduler(monkeypatch)

    monkeypatch.setattr(
        jobs_router,
        "list_jobs",
        lambda: [
            {
                "id": "discover_all",
                "name": "Discover",
                "description": "desc",
                "next_run_time": None,
                "trigger": "cron",
            }
        ],
    )

    client, _, _ = authorized_client
    resp = client.get("/api/jobs", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["id"] == "discover_all"


def test_jobs_api_run(monkeypatch, authorized_client):
    _enable_scheduler(monkeypatch)
    called = {}

    def fake_trigger(job_id, user_id=None):
        called["job_id"] = job_id
        called["user_id"] = user_id

    monkeypatch.setattr(jobs_router, "trigger_job", fake_trigger)

    client, _, _ = authorized_client
    resp = client.post(
        "/api/jobs/run",
        json={"job_id": "discover_all", "user_id": 1},
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 200
    assert called == {"job_id": "discover_all", "user_id": 1}


def test_jobs_api_reschedule(monkeypatch, authorized_client):
    _enable_scheduler(monkeypatch)
    captured = {}

    def fake_reschedule(job_id, cron):
        captured["job_id"] = job_id
        captured["cron"] = cron

    monkeypatch.setattr(jobs_router, "reschedule_job", fake_reschedule)

    client, _, _ = authorized_client
    resp = client.post(
        "/api/jobs/reschedule",
        json={"job_id": "discover_all", "cron": "0 12 * * *"},
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 200
    assert captured == {"job_id": "discover_all", "cron": "0 12 * * *"}
