"""
Authentication dependencies for FastAPI routes.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, TokenBlacklist
from .jwt import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def is_token_blacklisted(db: Session, jti: str) -> bool:
    """Return True when the given JTI exists in the token blacklist."""
    return db.query(TokenBlacklist).filter(TokenBlacklist.token_jti == jti).first() is not None


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Resolve the authenticated user from a bearer token.

    Steps:
    1) Decode JWT and extract subject (user id) and jti.
    2) Reject if token is blacklisted (revoked).
    3) Load the user from DB or raise 401.
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

