"""
Authentication router for GitHub OAuth flow.

Refactored to use:
- Core repositories for user management
- Token blacklist repository
- Cache invalidation on logout
- CSRF protection via OAuth state validation
- Account lockout protection against brute force
"""

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from core.cache import CacheKeys, cache
from core.logging import get_logger
from core.repositories import TokenBlacklistRepository, UserRepository
from core.security import get_account_lockout

from ..auth.dependencies import get_current_user
from ..auth.github_oauth import exchange_code_for_token, get_github_user, get_oauth_authorize_url
from ..auth.jwt import create_access_token, decode_access_token, get_token_expiry
from ..config import get_settings
from ..database import get_db
from ..models import User
from ..schemas import UserResponse

logger = get_logger("auth")

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def _get_client_ip(request: Request) -> str:
    """
    Get the client IP address from the request.

    Handles X-Forwarded-For header for reverse proxy setups.
    """
    # Check for forwarded header (common in reverse proxy setups)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP (original client)
        return forwarded.split(",")[0].strip()

    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"


# =============================================================================
# OAuth State Management (CSRF Protection)
# =============================================================================


class OAuthStateError(Exception):
    """Raised when Redis is unavailable for OAuth state management."""

    pass


def _store_oauth_state(state: str) -> bool:
    """
    Store OAuth state for CSRF validation.

    SECURITY: Requires Redis - no in-memory fallback to prevent security issues
    in multi-instance deployments where state wouldn't be shared.

    Args:
        state: Random state token

    Returns:
        True if stored successfully

    Raises:
        OAuthStateError: If Redis is unavailable
    """
    if not cache.is_available:
        logger.error(
            "oauth_state_store_failed",
            reason="Redis unavailable",
            message="OAuth requires Redis for secure state management",
        )
        raise OAuthStateError(
            "Authentication service temporarily unavailable. "
            "Redis is required for secure OAuth state management."
        )

    settings = get_settings()
    cache_key = CacheKeys.oauth_state(state)
    result = cache.set_json(cache_key, {"valid": True}, ttl=settings.oauth_state_ttl)
    if not result:
        raise OAuthStateError("Failed to store OAuth state")

    return True


def _validate_and_consume_oauth_state(state: str) -> bool:
    """
    Validate OAuth state and consume it (one-time use).

    SECURITY: Requires Redis - state validation is critical for CSRF protection.

    Args:
        state: State token from callback

    Returns:
        True if valid and consumed, False otherwise
    """
    if not state:
        return False

    if not cache.is_available:
        logger.error(
            "oauth_state_validate_failed",
            reason="Redis unavailable",
            message="Cannot validate OAuth state without Redis",
        )
        return False

    cache_key = CacheKeys.oauth_state(state)
    data = cache.get_json(cache_key)
    if data and data.get("valid"):
        cache.delete(cache_key)
        return True

    return False


# =============================================================================
# Auth Code Exchange (Prevents Token in URL)
# =============================================================================


def _store_auth_code(code: str, token: str, user_id: int) -> bool:
    """
    Store a temporary auth code that can be exchanged for a JWT token.

    SECURITY: Requires Redis - no in-memory fallback to ensure codes work
    across multiple server instances and are properly expired.

    Args:
        code: Random auth code
        token: JWT token to store
        user_id: User ID for logging

    Returns:
        True if stored successfully

    Raises:
        OAuthStateError: If Redis is unavailable
    """
    if not cache.is_available:
        logger.error(
            "auth_code_store_failed",
            reason="Redis unavailable",
            user_id=user_id,
        )
        raise OAuthStateError(
            "Authentication service temporarily unavailable. "
            "Redis is required for secure token exchange."
        )

    settings = get_settings()
    cache_key = CacheKeys.auth_code(code)
    result = cache.set_json(
        cache_key,
        {"token": token, "user_id": user_id},
        ttl=settings.auth_code_ttl,
    )
    if not result:
        raise OAuthStateError("Failed to store auth code")

    return True


def _exchange_auth_code(code: str) -> tuple[str | None, int | None]:
    """
    Exchange an auth code for a JWT token (one-time use).

    SECURITY: Requires Redis - auth codes must be stored persistently
    and consumed atomically to prevent replay attacks.

    Args:
        code: Auth code from callback redirect

    Returns:
        Tuple of (token, user_id) or (None, None) if invalid/expired
    """
    if not code:
        return None, None

    if not cache.is_available:
        logger.error(
            "auth_code_exchange_failed",
            reason="Redis unavailable",
        )
        return None, None

    cache_key = CacheKeys.auth_code(code)
    data = cache.get_json(cache_key)
    if data:
        cache.delete(cache_key)
        return data.get("token"), data.get("user_id")

    return None, None


@router.get("/login")
def login():
    """
    Redirect to GitHub OAuth authorization page.

    Flow:
    1. User clicks login
    2. Generate and store CSRF state token in Redis
    3. Redirect to GitHub with state
    4. User authorizes
    5. GitHub redirects to /auth/callback with state
    6. Callback validates state before processing

    Security:
    - State token prevents CSRF attacks on OAuth flow
    - State is stored in Redis with 10-minute TTL (Redis required)
    - State is consumed on callback (one-time use)

    Raises:
        HTTPException: If Redis is unavailable
    """
    state = secrets.token_urlsafe(32)  # 32 bytes = 256 bits of entropy

    try:
        # Store state for validation in callback (Redis required)
        _store_oauth_state(state)
    except OAuthStateError as e:
        logger.error("login_redis_unavailable", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable. Please try again later.",
        )

    authorize_url = get_oauth_authorize_url(state)
    return RedirectResponse(url=authorize_url)


@router.get("/callback")
def oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(None),
    db: Session = Depends(get_db),
):
    """
    Handle GitHub OAuth callback.

    Security:
    - Account lockout protection against brute force
    - Validates OAuth state to prevent CSRF attacks
    - Returns a short-lived auth code instead of JWT in URL
    - JWT is obtained via POST /auth/token exchange

    Flow:
    1. Check account lockout status
    2. Validate state parameter (CSRF protection)
    3. Exchange GitHub code for access token
    4. Create/update user in database
    5. Generate JWT and store with auth code
    6. Redirect to frontend with auth code (not JWT)
    7. Clear lockout on success
    """
    settings = get_settings()
    frontend_url = settings.cors_allowed_origins.split(",")[0].strip()

    # Get client IP for lockout tracking
    client_ip = _get_client_ip(request)
    lockout = get_account_lockout()

    # Check if IP is locked out due to repeated failures
    lockout_status = lockout.check(client_ip)
    if lockout_status.is_locked:
        logger.warning(
            "oauth_callback_locked_out",
            client_ip=client_ip[:20],
            retry_after=lockout_status.retry_after,
        )
        return RedirectResponse(
            url=f"{frontend_url}/auth/callback?error=too_many_attempts&retry_after={lockout_status.retry_after}"
        )

    # CSRF Protection: Validate OAuth state
    if not _validate_and_consume_oauth_state(state):
        # Record failure for lockout tracking
        lockout.record_failure(client_ip)
        logger.warning(
            "oauth_state_invalid",
            has_state=bool(state),
            client_ip=client_ip[:20],
            message="Invalid or missing OAuth state - possible CSRF attack",
        )
        return RedirectResponse(url=f"{frontend_url}/auth/callback?error=authentication_failed")

    try:
        # Exchange code for GitHub token
        access_token = exchange_code_for_token(code)
        github_user = get_github_user(access_token)

        if not github_user.get("github_id"):
            # Record failure for lockout tracking
            lockout.record_failure(client_ip)
            logger.warning("oauth_missing_github_id", client_ip=client_ip[:20])
            return RedirectResponse(url=f"{frontend_url}/auth/callback?error=authentication_failed")

        # Use repository to create/update user
        # Note: access_token is encrypted by the repository before storage
        user_repo = UserRepository(db)
        user = user_repo.create_or_update_from_github(
            github_id=github_user["github_id"],
            github_username=github_user.get("github_username") or github_user.get("github_id"),
            email=github_user.get("email"),
            avatar_url=github_user.get("avatar_url"),
            access_token=access_token,
        )
        db.commit()

        # Clear lockout on successful authentication
        lockout.clear(client_ip)

        # Create JWT token
        jwt_token = create_access_token({"sub": str(user.id)})

        # Generate short-lived auth code (prevents JWT exposure in URL)
        # Redis is required for secure auth code storage
        auth_code = secrets.token_urlsafe(32)
        try:
            _store_auth_code(auth_code, jwt_token, user.id)
        except OAuthStateError:
            # Redis unavailable - redirect with error
            logger.error("oauth_auth_code_store_failed", user_id=user.id)
            return RedirectResponse(url=f"{frontend_url}/auth/callback?error=service_unavailable")

        logger.info("oauth_login_success", user_id=user.id, username=user.github_username)
        return RedirectResponse(url=f"{frontend_url}/auth/callback?code={auth_code}")

    except Exception as e:
        # Record failure for lockout tracking
        lockout.record_failure(client_ip)
        logger.error(
            "oauth_callback_error",
            error=str(e),
            error_type=type(e).__name__,
            client_ip=client_ip[:20],
        )
        return RedirectResponse(url=f"{frontend_url}/auth/callback?error=authentication_failed")


@router.post("/token")
def exchange_token(
    code: str = Query(...),
    response: Response = None,
):
    """
    Exchange an auth code for a JWT token.

    This is the secure way to obtain the JWT after OAuth callback.
    The auth code is short-lived (1 minute) and single-use.

    Security:
    - Auth code expires in 1 minute
    - Auth code is consumed on first use (cannot be replayed)
    - JWT is set as HttpOnly cookie (cannot be accessed by JavaScript)
    - Also returns token in body for backward compatibility during migration

    Args:
        code: Auth code from OAuth callback redirect

    Returns:
        JWT access token (in both cookie and response body)
    """

    token, user_id = _exchange_auth_code(code)

    if not token:
        logger.warning("auth_code_exchange_failed", message="Invalid or expired auth code")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication code",
        )

    logger.info("auth_code_exchanged", user_id=user_id)

    # Create response with HttpOnly cookie
    settings = get_settings()
    is_production = settings.env.lower() in ("production", "prod")

    response = JSONResponse(
        content={"access_token": token, "token_type": "bearer"},
    )

    # Set HttpOnly cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,  # Cannot be accessed by JavaScript
        secure=is_production,  # Only send over HTTPS in production
        samesite="lax",  # CSRF protection
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )

    # Generate and set CSRF token (for forms that need it)
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # JavaScript needs to read this
        secure=is_production,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )

    return response


@router.get("/me", response_model=UserResponse)
def current_user(user: User = Depends(get_current_user)) -> UserResponse:
    """Get current authenticated user."""
    return user


@router.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Invalidate the current JWT token.

    Adds token to blacklist, clears user cache, and removes auth cookies.
    Supports both Bearer token and HttpOnly cookie authentication.
    """
    settings = get_settings()
    is_production = settings.env.lower() in ("production", "prod")

    # Get token from Authorization header or cookie
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.cookies.get("access_token")

    if not token:
        # No token to blacklist, just clear cookies
        response = JSONResponse(content={"status": "logged_out"})
        response.delete_cookie(key="access_token", path="/", secure=is_production, samesite="lax")
        response.delete_cookie(key="csrf_token", path="/", secure=is_production, samesite="lax")
        return response

    try:
        payload = decode_access_token(token)
        jti = payload.get("jti")

        if jti:
            # Get token expiry
            expiry = get_token_expiry(token)
            if not expiry:
                expiry = datetime.now(timezone.utc)

            # Add to blacklist using repository
            blacklist_repo = TokenBlacklistRepository(db)
            blacklist_repo.blacklist_token(jti, expiry)
            db.commit()

        # Clear user cache
        cache.delete_pattern(CacheKeys.user_pattern(current_user.id))
    except Exception:
        pass  # Continue even if blacklist fails

    # Clear cookies
    response = JSONResponse(content={"status": "logged_out"})
    response.delete_cookie(
        key="access_token",
        path="/",
        secure=is_production,
        samesite="lax",
    )
    response.delete_cookie(
        key="csrf_token",
        path="/",
        secure=is_production,
        samesite="lax",
    )

    return response


@router.delete("/account")
def delete_account(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete user account and all associated data.

    WARNING: This is irreversible.
    """
    user_id = user.id

    # Delete user (cascade deletes related data)
    db.delete(user)
    db.commit()

    # Clear all cached data for user
    cache.delete_pattern(CacheKeys.user_pattern(user_id))

    return {"status": "account_deleted"}


@router.post("/refresh")
def refresh_token(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Refresh JWT token.

    SECURITY: Blacklists the old token before issuing a new one to prevent
    token reuse attacks. If the old token is compromised, it cannot be used
    again after refresh.

    Returns a new token with extended expiry (in both cookie and response body).
    Supports both Bearer token and HttpOnly cookie authentication.
    """
    settings = get_settings()
    is_production = settings.env.lower() in ("production", "prod")

    # Get token from Authorization header or cookie
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.cookies.get("access_token")

    try:
        # Decode old token to get JTI for blacklisting
        if token:
            payload = decode_access_token(token)
            old_jti = payload.get("jti")
        else:
            old_jti = None

        if old_jti:
            # Get token expiry for blacklist entry
            expiry = get_token_expiry(token)
            if not expiry:
                expiry = datetime.now(timezone.utc)

            # Blacklist the old token BEFORE issuing new one
            blacklist_repo = TokenBlacklistRepository(db)
            blacklist_repo.blacklist_token(old_jti, expiry)
            db.commit()

            logger.debug("refresh_old_token_blacklisted", jti=old_jti[:8])
    except Exception as e:
        # Log but continue - issuing new token is more important
        logger.warning("refresh_blacklist_failed", error=str(e))

    # Issue new token
    new_token = create_access_token({"sub": str(current_user.id)})

    # Create response with updated cookie
    response = JSONResponse(
        content={"access_token": new_token, "token_type": "bearer"},
    )

    # Set new HttpOnly cookie
    response.set_cookie(
        key="access_token",
        value=new_token,
        httponly=True,
        secure=is_production,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )

    # Update CSRF token
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=is_production,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )

    return response


@router.get("/health")
def auth_health():
    """Health check for auth service."""
    return {
        "status": "healthy",
        "cache_available": cache.is_available,
    }
