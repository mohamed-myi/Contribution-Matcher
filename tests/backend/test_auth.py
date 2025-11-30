import pytest

from backend.app.auth import github_oauth
from backend.app.routers import auth as auth_router
from backend.app.models import User


def test_auth_login_redirects_to_github(test_app_client):
    """Test that /auth/login redirects to GitHub OAuth."""
    client, _ = test_app_client
    resp = client.get("/api/auth/login", follow_redirects=False)
    # Should be a redirect to GitHub
    assert resp.status_code in (302, 307)
    assert "github.com/login/oauth/authorize" in resp.headers.get("location", "")


def test_auth_callback_creates_user_and_redirects(monkeypatch, test_app_client):
    """Test that /auth/callback creates user and redirects to frontend with token."""
    client, session_factory = test_app_client

    monkeypatch.setattr(auth_router, "exchange_code_for_token", lambda code: "access")
    monkeypatch.setattr(
        auth_router,
        "get_github_user",
        lambda token: {
            "github_id": "123",
            "github_username": "octocat",
            "email": "octo@example.com",
            "avatar_url": "http://example.com/avatar.png",
        },
    )

    resp = client.get("/api/auth/callback", params={"code": "dummy"}, follow_redirects=False)
    # Should redirect to frontend with token
    assert resp.status_code in (302, 307)
    location = resp.headers.get("location", "")
    assert "/auth/callback?token=" in location

    # User should be created in database
    session = session_factory()
    user = session.query(User).filter_by(github_id="123").one()
    assert user.github_username == "octocat"
    session.close()


def test_auth_me_protected(test_app_client):
    """Test that /auth/me requires authentication."""
    client, _ = test_app_client
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
