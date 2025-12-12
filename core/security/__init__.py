"""
Security module for Contribution Matcher.

Provides:
- Token encryption (Fernet)
- Configuration validation
- Rate limiting
- Account lockout protection
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .encryption import TokenEncryption, get_encryption_service
    from .rate_limiter import (
        AccountLockout,
        LockoutResult,
        RateLimiter,
        get_account_lockout,
        get_rate_limiter,
    )
    from .validation import SecurityConfigError, validate_security_config


def __getattr__(name: str) -> Any:
    """
    Lazy attribute loading to avoid import-time cycles.

    This module is imported early during settings/logging initialization; importing
    Redis/cache-backed rate limiting or encryption eagerly can create circular imports.
    """
    if name in {"TokenEncryption", "get_encryption_service"}:
        from .encryption import TokenEncryption, get_encryption_service

        return TokenEncryption if name == "TokenEncryption" else get_encryption_service

    if name in {
        "AccountLockout",
        "LockoutResult",
        "RateLimiter",
        "get_account_lockout",
        "get_rate_limiter",
    }:
        from .rate_limiter import (
            AccountLockout,
            LockoutResult,
            RateLimiter,
            get_account_lockout,
            get_rate_limiter,
        )

        return {
            "AccountLockout": AccountLockout,
            "LockoutResult": LockoutResult,
            "RateLimiter": RateLimiter,
            "get_account_lockout": get_account_lockout,
            "get_rate_limiter": get_rate_limiter,
        }[name]

    if name in {"SecurityConfigError", "validate_security_config"}:
        from .validation import SecurityConfigError, validate_security_config

        return SecurityConfigError if name == "SecurityConfigError" else validate_security_config

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)


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
