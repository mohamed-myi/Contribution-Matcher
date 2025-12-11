"""
Security module for Contribution Matcher.

Provides:
- Token encryption (Fernet)
- Configuration validation
- Rate limiting
- Account lockout protection
"""

from .encryption import TokenEncryption, get_encryption_service
from .rate_limiter import (
    AccountLockout,
    LockoutResult,
    RateLimiter,
    get_account_lockout,
    get_rate_limiter,
)
from .validation import SecurityConfigError, validate_security_config

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
