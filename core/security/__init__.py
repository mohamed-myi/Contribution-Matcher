"""
Security module for Contribution Matcher.

Provides:
- Token encryption (Fernet)
- Configuration validation
- Rate limiting
- Account lockout protection
"""

from .encryption import TokenEncryption, get_encryption_service
from .validation import validate_security_config, SecurityConfigError
from .rate_limiter import (
    RateLimiter,
    get_rate_limiter,
    AccountLockout,
    get_account_lockout,
    LockoutResult,
)

__all__ = [
    "TokenEncryption",
    "get_encryption_service",
    "validate_security_config",
    "SecurityConfigError",
    "RateLimiter",
    "get_rate_limiter",
    "AccountLockout",
    "get_account_lockout",
    "LockoutResult",
]
