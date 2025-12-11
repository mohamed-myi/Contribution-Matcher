"""
Staleness detection service for verifying issue status with GitHub.

Checks if issues are still open and marks them appropriately.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from core.api import github_api
from core.logging import get_logger

from ..models import Issue

logger = get_logger("api.staleness")


# GitHub close reason mapping
CLOSE_REASON_MAP = {
    "completed": "completed",
    "not_planned": "not_planned",
    "merged": "merged",
}


def verify_issue_status(db: Session, issue: Issue) -> dict:
    """
    Verify a single issue's status with GitHub API.

    Returns:
        Dict with verification result including:
        - verified: bool
        - status: 'open', 'closed', 'error'
        - close_reason: optional reason if closed
        - changed: bool - whether status changed
    """
    if not issue.url:
        return {"verified": False, "status": "error", "error": "No URL"}

    try:
        # Parse issue URL to get API endpoint
        parts = issue.url.replace("https://github.com/", "").split("/")
        if len(parts) < 4 or parts[2] != "issues":
            return {"verified": False, "status": "error", "error": "Invalid URL format"}

        owner, repo, issue_number = parts[0], parts[1], parts[3]
        api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"

        # Make API request using github_api module
        response = github_api._make_request(api_url)

        if not response:
            logger.warning("verification_failed", issue_id=issue.id, url=issue.url)
            return {"verified": False, "status": "error", "error": "API request failed"}

        data = response.json()
        github_state = data.get("state", "unknown")

        # Track if status changed
        previous_state = issue.github_state
        status_changed = previous_state != github_state

        # Update issue
        issue.last_verified_at = datetime.utcnow()
        issue.github_state = github_state

        result = {
            "verified": True,
            "status": github_state,
            "changed": status_changed,
            "previous_status": previous_state,
        }

        if github_state == "closed":
            # Get close reason if available
            state_reason = data.get("state_reason")  # GitHub API field
            close_reason = CLOSE_REASON_MAP.get(state_reason, state_reason)

            issue.is_active = False
            issue.closed_at = datetime.utcnow()
            issue.close_reason = close_reason

            result["close_reason"] = close_reason

            logger.info("issue_closed", issue_id=issue.id, reason=close_reason)
        else:
            # Issue is still open
            issue.is_active = True
            issue.closed_at = None
            issue.close_reason = None

        db.commit()

        return result

    except Exception as e:
        logger.error("verification_exception", issue_id=issue.id, error=str(e))
        return {"verified": False, "status": "error", "error": str(e)}


def bulk_verify_issues(
    db: Session,
    user_id: int,
    limit: int = 50,
    min_age_days: int = 7,
) -> dict:
    """
    Bulk verify issues that haven't been checked recently.

    Args:
        db: Database session
        user_id: User ID to verify issues for
        limit: Maximum number of issues to verify
        min_age_days: Only verify issues not checked in this many days

    Returns:
        Dict with summary of verification results
    """
    from datetime import timedelta

    from sqlalchemy import or_

    cutoff = datetime.utcnow() - timedelta(days=min_age_days)

    # Get issues that need verification
    issues = (
        db.query(Issue)
        .filter(
            Issue.user_id == user_id,
            Issue.is_active,
            or_(
                Issue.last_verified_at.is_(None),
                Issue.last_verified_at < cutoff,
            ),
        )
        .order_by(Issue.last_verified_at.asc().nullsfirst())
        .limit(limit)
        .all()
    )

    if not issues:
        return {
            "verified": 0,
            "still_open": 0,
            "now_closed": 0,
            "errors": 0,
            "message": "No issues need verification",
        }

    logger.info("bulk_verify_started", user_id=user_id, issue_count=len(issues))

    results = {
        "verified": 0,
        "still_open": 0,
        "now_closed": 0,
        "errors": 0,
        "closed_issues": [],
    }

    for issue in issues:
        result: dict = verify_issue_status(db, issue)

        if result.get("verified"):
            results["verified"] += 1

            if result.get("status") == "open":
                results["still_open"] += 1
            elif result.get("status") == "closed":
                results["now_closed"] += 1
                closed_issues_list = results.get("closed_issues", [])
                if isinstance(closed_issues_list, list):
                    closed_issues_list.append(
                        {
                            "id": issue.id,
                            "title": issue.title,
                            "close_reason": result.get("close_reason"),
                        }
                    )
        else:
            results["errors"] += 1

    logger.info(
        "bulk_verify_complete",
        verified=results["verified"],
        still_open=results["still_open"],
        now_closed=results["now_closed"],
        errors=results["errors"],
    )

    return results


def get_stale_issues_count(db: Session, user_id: int) -> dict:
    """
    Get count of stale issues for a user.

    Returns counts for different staleness levels.
    """
    from datetime import timedelta

    from sqlalchemy import func

    now = datetime.utcnow()
    stale_cutoff = now - timedelta(days=7)
    very_stale_cutoff = now - timedelta(days=30)

    # Count never verified
    never_verified = (
        db.query(func.count(Issue.id))
        .filter(
            Issue.user_id == user_id,
            Issue.is_active,
            Issue.last_verified_at.is_(None),
        )
        .scalar()
    )

    # Count stale (7+ days)
    stale = (
        db.query(func.count(Issue.id))
        .filter(
            Issue.user_id == user_id,
            Issue.is_active,
            Issue.last_verified_at.isnot(None),
            Issue.last_verified_at < stale_cutoff,
        )
        .scalar()
    )

    # Count very stale (30+ days)
    very_stale = (
        db.query(func.count(Issue.id))
        .filter(
            Issue.user_id == user_id,
            Issue.is_active,
            Issue.last_verified_at.isnot(None),
            Issue.last_verified_at < very_stale_cutoff,
        )
        .scalar()
    )

    return {
        "never_verified": never_verified or 0,
        "stale": stale or 0,
        "very_stale": very_stale or 0,
        "total_needing_verification": (never_verified or 0) + (stale or 0),
    }


def mark_issues_closed(
    db: Session,
    issue_ids: list[int],
    close_reason: str = "manual",
) -> int:
    """
    Manually mark issues as closed.

    Returns number of issues updated.
    """
    now = datetime.utcnow()

    result = (
        db.query(Issue)
        .filter(Issue.id.in_(issue_ids))
        .update(
            {
                "is_active": False,
                "github_state": "closed",
                "closed_at": now,
                "close_reason": close_reason,
                "last_verified_at": now,
            },
            synchronize_session=False,
        )
    )

    db.commit()
    return result
