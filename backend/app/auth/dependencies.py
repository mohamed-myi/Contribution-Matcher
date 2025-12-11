"""
Authentication dependencies for FastAPI routes.

Supports both:
- Bearer token in Authorization header (for API clients)
- HttpOnly cookie (for browser-based frontends)
"""

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import TokenBlacklist, User
from .jwt import decode_access_token

# Standard OAuth2 scheme for backward compatibility
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def is_token_blacklisted(db: Session, jti: str) -> bool:
    """Return True when the given JTI exists in the token blacklist."""
    return db.query(TokenBlacklist).filter(TokenBlacklist.token_jti == jti).first() is not None


def get_token_from_request(
    request: Request,
    token_header: str | None = Depends(oauth2_scheme),
    access_token_cookie: str | None = Cookie(None, alias="access_token"),
) -> str:
    """
    Extract JWT token from request.

    Checks in order:
    1. Authorization header (Bearer token)
    2. HttpOnly cookie (access_token)

    This allows both API clients and browser frontends to authenticate.
    """
    # Prefer Authorization header if present
    if token_header:
        return token_header

    # Fall back to cookie
    if access_token_cookie:
        return access_token_cookie

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str = Depends(get_token_from_request),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolve the authenticated user from a bearer token or cookie.

    Steps:
    1) Extract token from header or cookie
    2) Decode JWT and extract subject (user id) and jti.
    3) Reject if token is blacklisted (revoked).
    4) Load the user from DB or raise 401.
    """
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        ) from None

    # Check if token is blacklisted
    jti = payload.get("jti")
    if jti and is_token_blacklisted(db, jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_optional_user(
    request: Request,
    token_header: str | None = Depends(oauth2_scheme),
    access_token_cookie: str | None = Cookie(None, alias="access_token"),
    db: Session = Depends(get_db),
) -> User | None:
    """
    Get the current user if authenticated, otherwise return None.

    Useful for endpoints that behave differently for authenticated users.
    """
    token = token_header or access_token_cookie

    if not token:
        return None

    try:
        payload = decode_access_token(token)

        # Check blacklist
        jti = payload.get("jti")
        if jti and is_token_blacklisted(db, jti):
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        return db.query(User).filter(User.id == int(user_id)).first()
    except ValueError:
        return None
