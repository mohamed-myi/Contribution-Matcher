from backend.app.models import User
from backend.app.routers import auth as auth_router


def test_auth_login_redirects_to_github(test_app_client):
    """Test that /auth/login redirects to GitHub OAuth."""
    client, _ = test_app_client
    resp = client.get("/api/v1/auth/login", follow_redirects=False)
    # Should be a redirect to GitHub
    assert resp.status_code in (302, 307)
    location = resp.headers.get("location", "")
    assert "github.com/login/oauth/authorize" in location
    # Should include state parameter for CSRF protection
    assert "state=" in location


def test_auth_callback_rejects_missing_state(test_app_client):
    """Test that /auth/callback rejects requests without valid OAuth state (CSRF protection)."""
    client, _ = test_app_client

    # Callback without state should be rejected
    resp = client.get("/api/v1/auth/callback", params={"code": "dummy"}, follow_redirects=False)
    assert resp.status_code in (302, 307)
    location = resp.headers.get("location", "")
    # Should redirect to frontend with error
    assert "error=authentication_failed" in location


def test_auth_callback_rejects_invalid_state(test_app_client):
    """Test that /auth/callback rejects invalid OAuth state."""
    client, _ = test_app_client

    # Callback with invalid state should be rejected
    resp = client.get(
        "/api/v1/auth/callback",
        params={"code": "dummy", "state": "invalid_state_token"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 307)
    location = resp.headers.get("location", "")
    # Should redirect to frontend with error
    assert "error=authentication_failed" in location


def test_auth_callback_creates_user_with_valid_state(monkeypatch, test_app_client):
    """Test that /auth/callback creates user and returns auth code (secure flow)."""
    client, session_factory = test_app_client

    # Mock GitHub API calls
    monkeypatch.setattr(auth_router, "exchange_code_for_token", lambda code: "access")  # noqa: ARG005
    monkeypatch.setattr(
        auth_router,
        "get_github_user",
        lambda token: {  # noqa: ARG005
            "github_id": "123",
            "github_username": "octocat",
            "email": "octo@example.com",
            "avatar_url": "http://example.com/avatar.png",
        },
    )

    # Mock the OAuth state validation to return True (simulating valid state)
    monkeypatch.setattr(
        auth_router,
        "_validate_and_consume_oauth_state",
        lambda state: True,  # noqa: ARG005
    )

    resp = client.get(
        "/api/v1/auth/callback",
        params={"code": "dummy", "state": "valid_test_state"},
        follow_redirects=False,
    )
    # Should redirect to frontend with auth code (not token in URL)
    # Auth code is then exchanged for JWT via POST /auth/token
    assert resp.status_code in (302, 307)
    location = resp.headers.get("location", "")
    assert "/auth/callback?code=" in location
    # Should NOT have token in URL (security: JWT should not be in URL)
    assert "token=" not in location

    # User should be created in database
    session = session_factory()
    user = session.query(User).filter_by(github_id="123").one()
    assert user.github_username == "octocat"
    session.close()


def test_auth_callback_uses_code_exchange_when_redis_available(monkeypatch, test_app_client):
    """Test that /auth/callback returns auth code when Redis is available (secure flow)."""
    client, session_factory = test_app_client

    # Mock GitHub API calls
    monkeypatch.setattr(auth_router, "exchange_code_for_token", lambda code: "access")  # noqa: ARG005
    monkeypatch.setattr(
        auth_router,
        "get_github_user",
        lambda token: {  # noqa: ARG005
            "github_id": "456",
            "github_username": "secureuser",
            "email": "secure@example.com",
            "avatar_url": "http://example.com/avatar.png",
        },
    )

    # Mock the OAuth state validation
    monkeypatch.setattr(
        auth_router,
        "_validate_and_consume_oauth_state",
        lambda state: True,  # noqa: ARG005
    )

    # Mock auth code storage to return True (simulating Redis available)
    monkeypatch.setattr(
        auth_router,
        "_store_auth_code",
        lambda code, token, user_id: True,  # noqa: ARG005
    )

    resp = client.get(
        "/api/v1/auth/callback",
        params={"code": "dummy", "state": "valid_test_state"},
        follow_redirects=False,
    )
    # Should redirect to frontend with auth CODE (not token) - secure flow
    assert resp.status_code in (302, 307)
    location = resp.headers.get("location", "")
    # Should have code parameter, NOT token
    assert "/auth/callback?code=" in location
    assert "token=" not in location

    # User should be created in database
    session = session_factory()
    user = session.query(User).filter_by(github_id="456").one()
    assert user.github_username == "secureuser"
    session.close()


def test_auth_token_exchange_success(monkeypatch, test_app_client):
    """Test that /auth/token exchanges auth code for JWT."""
    client, _ = test_app_client

    # Mock the auth code exchange to return a valid token
    monkeypatch.setattr(
        auth_router,
        "_exchange_auth_code",
        lambda code: ("jwt_token_here", 123),  # noqa: ARG005
    )

    resp = client.post("/api/v1/auth/token", params={"code": "valid_auth_code"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "jwt_token_here"
    assert data["token_type"] == "bearer"


def test_auth_token_exchange_invalid_code(monkeypatch, test_app_client):
    """Test that /auth/token rejects invalid auth codes."""
    client, _ = test_app_client

    # Mock the auth code exchange to return None (invalid code)
    monkeypatch.setattr(
        auth_router,
        "_exchange_auth_code",
        lambda code: (None, None),  # noqa: ARG005
    )

    resp = client.post("/api/v1/auth/token", params={"code": "invalid_code"})
    assert resp.status_code == 401


def test_auth_me_protected(test_app_client):
    """Test that /auth/me requires authentication."""
    client, _ = test_app_client
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


# =============================================================================
# Account Lockout Tests
# =============================================================================


class TestAccountLockout:
    """Tests for account lockout mechanism."""

    def test_lockout_after_repeated_failures(self):
        """Test that account gets locked out after repeated authentication failures."""
        from core.security import AccountLockout

        # Create a fresh lockout instance for testing
        lockout = AccountLockout()
        test_ip = "192.168.1.100"
        # Clear any existing state from previous test runs
        lockout.clear(test_ip)

        # Initially not locked
        result = lockout.check(test_ip)
        assert not result.is_locked
        assert result.failure_count == 0

        # Record failures - should not be locked after 2 failures
        lockout.record_failure(test_ip)
        lockout.record_failure(test_ip)
        result = lockout.check(test_ip)
        assert not result.is_locked
        assert result.failure_count == 2

        # After 3rd failure, should be locked for 1 minute
        result = lockout.record_failure(test_ip)
        assert result.is_locked
        assert result.failure_count == 3
        assert result.retry_after == 60  # 1 minute

    def test_lockout_progressive_duration(self):
        """Test that lockout duration increases with more failures."""
        from core.security import AccountLockout

        lockout = AccountLockout()
        test_ip = "192.168.1.101"
        # Clear any existing state from previous test runs
        lockout.clear(test_ip)

        # Record 3 failures -> 1 minute lockout
        for _ in range(3):
            result = lockout.record_failure(test_ip)
        assert result.retry_after == 60

        # Record 2 more (5 total) -> 5 minute lockout
        for _ in range(2):
            result = lockout.record_failure(test_ip)
        assert result.retry_after == 300  # 5 minutes

        # Record 2 more (7 total) -> 15 minute lockout
        for _ in range(2):
            result = lockout.record_failure(test_ip)
        assert result.retry_after == 900  # 15 minutes

        # Record 3 more (10 total) -> 1 hour lockout
        for _ in range(3):
            result = lockout.record_failure(test_ip)
        assert result.retry_after == 3600  # 1 hour

    def test_lockout_clear_on_success(self):
        """Test that lockout is cleared after successful authentication."""
        from core.security import AccountLockout

        lockout = AccountLockout()
        test_ip = "192.168.1.102"

        # Create some failures
        for _ in range(5):
            lockout.record_failure(test_ip)

        result = lockout.check(test_ip)
        assert result.is_locked
        assert result.failure_count == 5

        # Clear on success
        lockout.clear(test_ip)

        # Should be unlocked with 0 failures
        result = lockout.check(test_ip)
        assert not result.is_locked
        assert result.failure_count == 0

    def test_lockout_blocks_oauth_callback(self, monkeypatch, test_app_client):
        """Test that locked out IPs are blocked from OAuth callback."""
        from unittest.mock import MagicMock

        from core.security import AccountLockout

        client, _ = test_app_client

        # Create a mock lockout that always reports locked
        mock_lockout = MagicMock(spec=AccountLockout)
        mock_lockout.check.return_value = MagicMock(
            is_locked=True,
            failure_count=10,
            lockout_until=9999999999,
            retry_after=3600,
        )

        # Patch the singleton to return our mock
        monkeypatch.setattr(
            "backend.app.routers.auth.get_account_lockout",
            lambda: mock_lockout,
        )

        # Attempt OAuth callback
        resp = client.get(
            "/api/v1/auth/callback",
            params={"code": "any_code", "state": "any_state"},
            follow_redirects=False,
        )

        assert resp.status_code in (302, 307)
        location = resp.headers.get("location", "")
        assert "error=too_many_attempts" in location
        assert "retry_after=3600" in location

    def test_lockout_different_ips_independent(self):
        """Test that different IPs have independent lockout tracking."""
        from core.security import AccountLockout

        lockout = AccountLockout()
        ip1 = "192.168.1.200"
        ip2 = "192.168.1.201"

        # Lock out ip1
        for _ in range(5):
            lockout.record_failure(ip1)

        # ip1 should be locked
        assert lockout.check(ip1).is_locked

        # ip2 should not be locked
        assert not lockout.check(ip2).is_locked
        assert lockout.check(ip2).failure_count == 0
