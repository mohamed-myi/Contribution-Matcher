"""
Rate limiting dependencies using the core Redis-backed limiter.
"""

from fastapi import Depends, HTTPException, Request, Response, status

from core.logging import get_logger
from core.security import get_rate_limiter

from ..auth.dependencies import get_current_user
from ..models import User

logger = get_logger("api.rate_limit")


def _check_limit(
    endpoint_type: str,
    identifier: str,
    response: Response | None = None,
) -> None:
    """
    Common logic to check rate limit and set headers.
    """
    limiter = get_rate_limiter()

    # Check limit
    result = limiter.check(endpoint_type, identifier)

    # Set headers if response object is available
    if response:
        headers = result.to_headers()
        for key, value in headers.items():
            response.headers[key] = value

    if not result.allowed:
        logger.warning(
            "rate_limit_exceeded",
            endpoint=endpoint_type,
            identifier=identifier[:20],  # Truncate potentially sensitive ID
            retry_after=result.retry_after,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {result.retry_after} seconds.",
            headers={"Retry-After": str(result.retry_after)} if result.retry_after else {},
        )


def enforce_rate_limit(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
):
    """
    Enforce rate limits for authenticated users.

    Uses 'api' configuration (e.g. 100/min).
    Key: user:{id}
    """
    _check_limit("api", f"user:{user.id}", response)


def enforce_public_rate_limit(
    request: Request,
    response: Response,
):
    """
    Enforce rate limits for public endpoints based on IP.

    Uses 'auth' configuration (e.g. 5/5min).
    Key: ip:{ip_address}
    """
    # Handle reverse proxy headers if present
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    _check_limit("auth", f"ip:{client_ip}", response)
