"""
JWT helper utilities.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from jose import JWTError, jwt

from ..config import get_settings


def create_access_token(data: Dict[str, Any], expires_minutes: int | None = None) -> str:
    """
    Create a signed JWT access token with expiration and JTI.

    Args:
        data: Claims to include in the token (e.g., {"sub": user_id}).
        expires_minutes: Optional override for expiration window in minutes.

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    to_encode = data.copy()
    expire_delta = timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    expire = datetime.now(timezone.utc) + expire_delta
    # Add JWT ID for token invalidation
    to_encode.update({
        "exp": expire,
        "jti": str(uuid.uuid4()),
    })
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Args:
        token: Encoded JWT string.

    Returns:
        Decoded payload dict.

    Raises:
        ValueError: If token is invalid or signature/expiry check fails.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as exc:
        raise ValueError("Invalid token") from exc


def get_token_expiry(token: str) -> datetime | None:
    """Get the expiration datetime from a token."""
    try:
        payload = decode_access_token(token)
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
        return None
    except ValueError:
        return None

