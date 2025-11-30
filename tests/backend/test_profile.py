from backend.app.models import DevProfile


def test_update_profile_creates_entry(authorized_client):
    client, _, session_factory = authorized_client

    payload = {
        "skills": ["python", "react"],
        "experience_level": "intermediate",
        "interests": ["open-source"],
        "preferred_languages": ["python"],
        "time_availability": 10,
    }

    resp = client.put(
        "/api/profile",
        json=payload,
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["skills"] == ["python", "react"]

    session = session_factory()
    profile = session.query(DevProfile).filter(DevProfile.user_id == 1).one()
    assert profile.experience_level == "intermediate"
    session.close()


def test_get_profile_returns_data(authorized_client):
    client, _, session_factory = authorized_client
    session = session_factory()
    session.add(
        DevProfile(
            user_id=1,
            skills=["python"],
            experience_level="advanced",
            interests=["ai"],
            preferred_languages=["python"],
        )
    )
    session.commit()
    session.close()

    resp = client.get(
        "/api/profile",
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["experience_level"] == "advanced"


def test_create_profile_from_github(authorized_client, monkeypatch):
    """Test creating profile from GitHub data."""
    client, _, session_factory = authorized_client

    # Mock the httpx call
    import httpx
    
    class MockResponse:
        status_code = 200
        def json(self):
            return [
                {"language": "Python", "topics": ["web", "api"]},
                {"language": "JavaScript", "topics": ["frontend"]},
            ]
    
    class MockClient:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, *args, **kwargs):
            return MockResponse()
    
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: MockClient())

    resp = client.post(
        "/api/profile/from-github",
        json={},
        headers={"Authorization": "Bearer fake"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "skills" in data
    assert "id" in data
