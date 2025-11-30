"""
Authentication router for GitHub OAuth flow.

Refactored to use:
- Core repositories for user management
- Token blacklist repository
- Cache invalidation on logout
"""

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from core.repositories import UserRepository, TokenBlacklistRepository
from core.cache import cache, CacheKeys

from ..auth.github_oauth import exchange_code_for_token, get_github_user, get_oauth_authorize_url
from ..auth.jwt import create_access_token, decode_access_token, get_token_expiry
from ..auth.dependencies import get_current_user
from ..config import get_settings
from ..database import get_db
from ..models import User
from ..schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@router.get("/login")
def login():
    """
    Redirect to GitHub OAuth authorization page.
    
    Flow:
    1. User clicks login
    2. Redirect to GitHub
    3. User authorizes
    4. GitHub redirects to /auth/callback
    """
    state = secrets.token_urlsafe(16)
    authorize_url = get_oauth_authorize_url(state)
    return RedirectResponse(url=authorize_url)


@router.get("/callback")
def oauth_callback(
    code: str = Query(...),
    state: str = Query(None),
    db: Session = Depends(get_db),
):
    """
    Handle GitHub OAuth callback.
    
    - Exchange code for GitHub access token
    - Fetch user info from GitHub
    - Create or update user in database
    - Generate JWT and redirect to frontend
    """
    settings = get_settings()
    
    try:
        # Exchange code for GitHub token
        access_token = exchange_code_for_token(code)
        github_user = get_github_user(access_token)

        if not github_user.get("github_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub user missing id",
            )

        # Use repository to create/update user
        user_repo = UserRepository(db)
        user = user_repo.create_or_update_from_github(
            github_id=github_user["github_id"],
            github_username=github_user.get("github_username") or github_user.get("github_id"),
            email=github_user.get("email"),
            avatar_url=github_user.get("avatar_url"),
            access_token=access_token,
        )
        db.commit()

        # Create JWT token
        token = create_access_token({"sub": str(user.id)})
        
        # Redirect to frontend with token
        frontend_url = settings.cors_allowed_origins.split(",")[0].strip()
        return RedirectResponse(url=f"{frontend_url}/auth/callback?token={token}")
        
    except Exception as e:
        # Redirect to frontend with error
        frontend_url = settings.cors_allowed_origins.split(",")[0].strip()
        return RedirectResponse(url=f"{frontend_url}/auth/callback?error={str(e)}")


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
