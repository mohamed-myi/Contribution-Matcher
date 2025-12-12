from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def test_new_model_timestamps_are_timezone_aware(test_session):
    """
    Phase 4 regression test: new model defaults should be created using timezone-aware UTC.

    Note: SQLite/SQLAlchemy may coerce datetimes on round-trip; we assert the in-Python
    value assigned by defaults is timezone-aware at creation/flush time.
    """
    from core.models import User

    user = User(
        github_id="phase4_user_1",
        github_username="phase4user",
        email="phase4@example.com",
    )
    test_session.add(user)
    test_session.flush()

    assert user.created_at is not None
    assert user.created_at.tzinfo is not None
    assert user.created_at.utcoffset() == timezone.utc.utcoffset(user.created_at)


def test_issue_is_stale_handles_naive_last_verified_at():
    """Phase 4 regression: mixed naive/aware comparisons must not raise TypeError."""
    from core.models import Issue

    issue = Issue(
        user_id=1,
        title="Test",
        url="https://example.com/issues/1",
        last_verified_at=datetime.now(),  # naive on purpose
        is_active=True,
    )

    # Should not raise (TypeError) and should return a boolean.
    assert isinstance(issue.is_stale, bool)


def test_github_api_make_request_retries_at_most_once(monkeypatch):
    """
    Phase 4 regression: _make_request must not recurse unboundedly on 403/rate limit.

    Assert: one retry max => requests.get called exactly twice when first call is 403.
    """
    from core.api import github_api

    reset_ts = int(github_api.time.time()) + 1

    # Mock response objects
    resp_403 = SimpleNamespace(
        status_code=403,
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset_ts)},
    )
    # On the retry call, also return 403 to prove the guard stops further recursion
    resp_403_b = SimpleNamespace(
        status_code=403,
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset_ts)},
    )

    mock_get = Mock(side_effect=[resp_403, resp_403_b])
    monkeypatch.setattr(github_api.requests, "get", mock_get)

    mock_sleep = Mock()
    monkeypatch.setattr(github_api.time, "sleep", mock_sleep)

    result = github_api._make_request("https://api.github.com/test")

    assert result is None
    assert mock_get.call_count == 2
    # Sleep may happen in _wait_for_rate_limit + retry branch; the key invariant is single retry.
    assert mock_sleep.call_count >= 1


def test_config_validation_reuses_security_validation(monkeypatch):
    """
    Phase 4 regression: config JWT validation should reuse core.security.validation.validate_jwt_secret.
    """
    from core.config import Settings

    # Development: invalid secret should warn but not fail
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("JWT_SECRET_KEY", "CHANGE_ME")
    with pytest.warns(UserWarning):
        Settings()

    # Production: invalid secret should raise during settings validation
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "CHANGE_ME")
    with pytest.raises(ValueError):
        Settings()

    # validate_production_config should also use the canonical validator result
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("JWT_SECRET_KEY", "CHANGE_ME")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "x")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "y")
    monkeypatch.setenv("PAT_TOKEN", "z")
    s = Settings()
    errors, warnings = s.validate_production_config()
    assert errors == []
    assert any("JWT_SECRET_KEY" in w for w in warnings)
