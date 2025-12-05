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

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from core.repositories import UserRepository, TokenBlacklistRepository
from core.cache import cache, CacheKeys
from core.logging import get_logger
from core.security import get_account_lockout

from ..auth.github_oauth import exchange_code_for_token, get_github_user, get_oauth_authorize_url
from ..auth.jwt import create_access_token, decode_access_token, get_token_expiry
from ..auth.dependencies import get_current_user
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

import threading
import time

# In-memory fallback for OAuth state when Redis is unavailable
_oauth_state_store: dict[str, float] = {}  # state -> expiry timestamp
_oauth_state_lock = threading.Lock()
_OAUTH_STATE_TTL = 600  # 10 minutes


def _cleanup_expired_states() -> None:
    """Remove expired states from in-memory store."""
    now = time.time()
    expired = [s for s, exp in _oauth_state_store.items() if exp < now]
    for s in expired:
        _oauth_state_store.pop(s, None)


def _store_oauth_state(state: str) -> bool:
    """
    Store OAuth state for CSRF validation.
    
    Uses Redis if available, otherwise falls back to in-memory storage.
    This prevents CSRF attacks on the OAuth flow.
    
    Args:
        state: Random state token
        
    Returns:
        True if stored successfully, False otherwise
    """
    # Try Redis first
    if cache.is_available:
        cache_key = CacheKeys.oauth_state(state)
        result = cache.set_json(cache_key, {"valid": True}, ttl=CacheKeys.TTL_OAUTH_STATE)
        if result:
            return True
    
    # Fallback to in-memory storage
    with _oauth_state_lock:
        _cleanup_expired_states()
        _oauth_state_store[state] = time.time() + _OAUTH_STATE_TTL
        logger.debug("oauth_state_stored_memory", state_prefix=state[:8])
    return True


def _validate_and_consume_oauth_state(state: str) -> bool:
    """
    Validate OAuth state and consume it (one-time use).
    
    Checks both Redis and in-memory storage.
    
    Args:
        state: State token from callback
        
    Returns:
        True if valid and consumed, False otherwise
    """
    if not state:
        return False
    
    # Try Redis first
    if cache.is_available:
        cache_key = CacheKeys.oauth_state(state)
        data = cache.get_json(cache_key)
        if data and data.get("valid"):
            cache.delete(cache_key)
            return True
    
    # Check in-memory fallback
    with _oauth_state_lock:
        _cleanup_expired_states()
        if state in _oauth_state_store:
            expiry = _oauth_state_store.pop(state)
            if expiry > time.time():
                logger.debug("oauth_state_validated_memory", state_prefix=state[:8])
                return True
    
    return False


# =============================================================================
# Auth Code Exchange (Prevents Token in URL)
# =============================================================================

# In-memory fallback for auth codes when Redis is unavailable
_auth_code_store: dict[str, dict] = {}  # code -> {token, user_id, expiry}
_auth_code_lock = threading.Lock()
_AUTH_CODE_TTL = 60  # 1 minute


def _cleanup_expired_auth_codes() -> None:
    """Remove expired auth codes from in-memory store."""
    now = time.time()
    expired = [c for c, data in _auth_code_store.items() if data.get("expiry", 0) < now]
    for c in expired:
        _auth_code_store.pop(c, None)


def _store_auth_code(code: str, token: str, user_id: int) -> bool:
    """
    Store a temporary auth code that can be exchanged for a JWT token.
    
    Uses Redis if available, otherwise falls back to in-memory storage.
    This prevents the JWT from being exposed in URL query parameters,
    which could leak via browser history, server logs, or Referer headers.
    
    Args:
        code: Random auth code
        token: JWT token to store
        user_id: User ID for logging
        
    Returns:
        True if stored successfully, False otherwise
    """
    # Try Redis first
    if cache.is_available:
        cache_key = CacheKeys.auth_code(code)
        result = cache.set_json(
            cache_key,
            {"token": token, "user_id": user_id},
            ttl=CacheKeys.TTL_AUTH_CODE,
        )
        if result:
            return True
    
    # Fallback to in-memory storage
    with _auth_code_lock:
        _cleanup_expired_auth_codes()
        _auth_code_store[code] = {
            "token": token,
            "user_id": user_id,
            "expiry": time.time() + _AUTH_CODE_TTL,
        }
        logger.debug("auth_code_stored_memory", user_id=user_id)
    return True


def _exchange_auth_code(code: str) -> tuple[str | None, int | None]:
    """
    Exchange an auth code for a JWT token (one-time use).
    
    Checks both Redis and in-memory storage.
    
    Args:
        code: Auth code from callback redirect
        
    Returns:
        Tuple of (token, user_id) or (None, None) if invalid/expired
    """
    if not code:
        return None, None
    
    # Try Redis first
    if cache.is_available:
        cache_key = CacheKeys.auth_code(code)
        data = cache.get_json(cache_key)
        if data:
            cache.delete(cache_key)
            return data.get("token"), data.get("user_id")
    
    # Check in-memory fallback
    with _auth_code_lock:
        _cleanup_expired_auth_codes()
        if code in _auth_code_store:
            data = _auth_code_store.pop(code)
            if data.get("expiry", 0) > time.time():
                logger.debug("auth_code_exchanged_memory", user_id=data.get("user_id"))
                return data.get("token"), data.get("user_id")
    
    return None, None


@router.get("/login")
def login():
    """
    Redirect to GitHub OAuth authorization page.
    
    Flow:
    1. User clicks login
    2. Generate and store CSRF state token (Redis or in-memory)
    3. Redirect to GitHub with state
    4. User authorizes
    5. GitHub redirects to /auth/callback with state
    6. Callback validates state before processing
    
    Security:
    - State token prevents CSRF attacks on OAuth flow
    - State is stored in Redis (or in-memory fallback) with 10-minute TTL
    - State is consumed on callback (one-time use)
    """
    state = secrets.token_urlsafe(32)  # 32 bytes = 256 bits of entropy
    
    # Store state for validation in callback (uses in-memory fallback if Redis unavailable)
    _store_oauth_state(state)
    
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
        return RedirectResponse(
            url=f"{frontend_url}/auth/callback?error=authentication_failed"
        )
    
    try:
        # Exchange code for GitHub token
        access_token = exchange_code_for_token(code)
        github_user = get_github_user(access_token)

        if not github_user.get("github_id"):
            # Record failure for lockout tracking
            lockout.record_failure(client_ip)
            logger.warning("oauth_missing_github_id", client_ip=client_ip[:20])
            return RedirectResponse(
                url=f"{frontend_url}/auth/callback?error=authentication_failed"
            )

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
        # Uses Redis if available, otherwise in-memory fallback
        auth_code = secrets.token_urlsafe(32)
        _store_auth_code(auth_code, jwt_token, user.id)
        
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
        return RedirectResponse(
            url=f"{frontend_url}/auth/callback?error=authentication_failed"
        )


@router.post("/token")
def exchange_token(code: str = Query(...)):
    """
    Exchange an auth code for a JWT token.
    
    This is the secure way to obtain the JWT after OAuth callback.
    The auth code is short-lived (1 minute) and single-use.
    
    Security:
    - Auth code expires in 1 minute
    - Auth code is consumed on first use (cannot be replayed)
    - JWT is never exposed in URLs or logs
    
    Args:
        code: Auth code from OAuth callback redirect
        
    Returns:
        JWT access token
    """
    token, user_id = _exchange_auth_code(code)
    
    if not token:
        logger.warning("auth_code_exchange_failed", message="Invalid or expired auth code")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication code",
        )
    
    logger.info("auth_code_exchanged", user_id=user_id)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def current_user(user: User = Depends(get_current_user)) -> UserResponse:
    """Get current authenticated user."""
    return user


@router.post("/logout")
def logout(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Invalidate the current JWT token.
    
    Adds token to blacklist and clears user cache.
    """
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
        
        return {"status": "logged_out"}
    except Exception:
        # Even if token is invalid, we return success
        return {"status": "logged_out"}


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
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
):
    """
    Refresh JWT token.
    
    Returns a new token with extended expiry.
    """
    new_token = create_access_token({"sub": str(current_user.id)})
    return {"access_token": new_token, "token_type": "bearer"}


@router.get("/health")
def auth_health():
    """Health check for auth service."""
    return {
        "status": "healthy",
        "cache_available": cache.is_available,
    }
