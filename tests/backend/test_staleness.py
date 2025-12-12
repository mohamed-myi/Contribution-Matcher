"""
Tests for issue staleness detection and verification.
"""

from datetime import datetime, timedelta, timezone

from backend.app.models import Issue


def create_test_issue(session, user_id=1, **kwargs):
    """Create a test issue with optional overrides."""
    defaults = {
        "user_id": user_id,
        "title": "Test Issue",
        "url": "https://github.com/test/repo/issues/1",
        "difficulty": "beginner",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    issue = Issue(**defaults)
    session.add(issue)
    session.commit()
    return issue


class TestStalenessProperties:
    """Tests for Issue staleness properties."""

    def test_is_stale_when_never_verified(self, authorized_client):
        """Issue should be stale if never verified."""
        _, _, session_factory = authorized_client
        session = session_factory()

        issue = create_test_issue(session, last_verified_at=None)

        assert issue.is_stale is True
        assert issue.is_very_stale is True

        session.close()

    def test_is_not_stale_when_recently_verified(self, authorized_client):
        """Issue should not be stale if verified within 7 days."""
        _, _, session_factory = authorized_client
        session = session_factory()

        issue = create_test_issue(
            session, last_verified_at=datetime.now(timezone.utc) - timedelta(days=3)
        )

        assert issue.is_stale is False
        assert issue.is_very_stale is False

        session.close()

    def test_is_stale_after_7_days(self, authorized_client):
        """Issue should be stale after 7 days without verification."""
        _, _, session_factory = authorized_client
        session = session_factory()

        issue = create_test_issue(
            session, last_verified_at=datetime.now(timezone.utc) - timedelta(days=10)
        )

        assert issue.is_stale is True
        assert issue.is_very_stale is False

        session.close()

    def test_is_very_stale_after_30_days(self, authorized_client):
        """Issue should be very stale after 30 days without verification."""
        _, _, session_factory = authorized_client
        session = session_factory()

        issue = create_test_issue(
            session, last_verified_at=datetime.now(timezone.utc) - timedelta(days=35)
        )

        assert issue.is_stale is True
        assert issue.is_very_stale is True

        session.close()


class TestStalenessStatsEndpoint:
    """Tests for staleness stats endpoint."""

    def test_get_staleness_stats_empty(self, authorized_client):
        """Staleness stats should return zeros when no issues."""
        client, _, _ = authorized_client

        resp = client.get(
            "/api/v1/issues/staleness-stats",
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["never_verified"] == 0
        assert data["stale"] == 0
        assert data["very_stale"] == 0

    def test_get_staleness_stats_with_issues(self, authorized_client):
        """Staleness stats should count issues correctly."""
        client, _, session_factory = authorized_client
        session = session_factory()

        now = datetime.now(timezone.utc)

        # Create issues with different verification states
        create_test_issue(
            session, url="https://github.com/test/repo/issues/1", last_verified_at=None
        )  # never verified
        create_test_issue(
            session,
            url="https://github.com/test/repo/issues/2",
            last_verified_at=now - timedelta(days=3),
        )  # fresh
        create_test_issue(
            session,
            url="https://github.com/test/repo/issues/3",
            last_verified_at=now - timedelta(days=10),
        )  # stale
        create_test_issue(
            session,
            url="https://github.com/test/repo/issues/4",
            last_verified_at=now - timedelta(days=35),
        )  # very stale

        session.close()

        resp = client.get(
            "/api/v1/issues/staleness-stats",
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["never_verified"] == 1
        assert data["stale"] == 2  # 10 days + 35 days (both > 7 days)
        assert data["very_stale"] == 1  # 35 days only


class TestVerifyStatusEndpoint:
    """Tests for issue verification endpoints."""

    def test_verify_status_issue_not_found(self, authorized_client):
        """Should return 404 for non-existent issue."""
        client, _, _ = authorized_client

        resp = client.post(
            "/api/v1/issues/99999/verify-status",
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 404

    def test_verify_status_invalid_url(self, authorized_client):
        """Should handle issues with invalid URLs."""
        client, _, session_factory = authorized_client
        session = session_factory()

        issue = create_test_issue(session, url="not-a-valid-url")
        issue_id = issue.id  # Get the ID before closing session
        session.close()

        resp = client.post(
            f"/api/v1/issues/{issue_id}/verify-status",
            headers={"Authorization": "Bearer fake"},
        )
        # Should return 502 for invalid URL
        assert resp.status_code == 502


class TestIssueResponseIncludesStaleness:
    """Tests that issue responses include staleness fields."""

    def test_issue_list_includes_staleness_fields(self, authorized_client):
        """Issue list response should include staleness fields."""
        client, _, session_factory = authorized_client
        session = session_factory()

        create_test_issue(
            session,
            url="https://github.com/test/repo/issues/1",
            last_verified_at=datetime.now(timezone.utc) - timedelta(days=10),
            github_state="open",
        )
        session.close()

        resp = client.get(
            "/api/v1/issues",
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["issues"]) == 1
        issue = data["issues"][0]

        assert "last_verified_at" in issue
        assert "github_state" in issue
        assert "is_stale" in issue
        assert "is_very_stale" in issue
        assert issue["is_stale"] is True
        assert issue["github_state"] == "open"


class TestMarkIssuesClosedAuthorization:
    """Tests for authorization enforcement in mark_issues_closed."""

    def test_mark_issues_closed_filters_by_user_id(self, authorized_client):
        """
        A user must not be able to close issues they don't own.

        mark_issues_closed() should only update rows where Issue.user_id matches.
        """
        _, current_user_fn, session_factory = authorized_client
        current_user = current_user_fn()

        from backend.app.services import staleness_service

        session = session_factory()
        try:
            # Create one issue for current user, one for another user
            issue_a = create_test_issue(
                session,
                user_id=current_user.id,
                url="https://github.com/test/repo/issues/100",
                github_state="open",
            )
            issue_b = create_test_issue(
                session,
                user_id=current_user.id + 999,
                url="https://github.com/test/repo/issues/200",
                github_state="open",
            )

            updated = staleness_service.mark_issues_closed(
                db=session,
                issue_ids=[issue_a.id, issue_b.id],
                user_id=current_user.id,
                close_reason="manual",
            )
            assert updated == 1

            session.refresh(issue_a)
            session.refresh(issue_b)

            assert issue_a.is_active is False
            assert issue_a.github_state == "closed"
            assert issue_b.is_active is True
            assert issue_b.github_state == "open"
        finally:
            session.close()
