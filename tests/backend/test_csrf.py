from backend.app.auth.jwt import create_access_token
from backend.app.models import User


def _create_user(session_factory) -> User:
    session = session_factory()
    try:
        user = User(
            github_id="csrf_user_1",
            github_username="csrf_tester",
            email="csrf_tester@example.com",
            avatar_url="http://example.com/avatar.png",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    finally:
        session.close()


def test_csrf_cookie_auth_requires_header(test_app_client):
    client, session_factory = test_app_client
    user = _create_user(session_factory)
    token = create_access_token({"sub": str(user.id)})

    # Simulate cookie-auth: access_token + csrf_token cookies present
    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", "csrf_test_token")

    # Missing X-CSRF-Token should be rejected
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 403

    # Correct header should succeed
    resp = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "csrf_test_token"})
    assert resp.status_code == 200
    assert resp.json().get("status") == "logged_out"


def test_csrf_bearer_auth_is_exempt(test_app_client):
    client, session_factory = test_app_client
    user = _create_user(session_factory)
    token = create_access_token({"sub": str(user.id)})

    # Bearer-token clients should not be forced to send CSRF header
    resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json().get("status") == "logged_out"
