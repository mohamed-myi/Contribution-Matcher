"""
Security configuration validation.

Ensures critical security settings are properly configured
before the application starts.
"""

import os
import re
from dataclasses import dataclass

from core.logging import get_logger

logger = get_logger("security.validation")


class SecurityConfigError(Exception):
    """Raised when security configuration is invalid."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        message = "Security configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)


@dataclass
class ValidationResult:
    """Result of security validation."""

    valid: bool
    errors: list[str]
    warnings: list[str]


def validate_jwt_secret(secret: str) -> tuple[bool, str | None]:
    """
    Validate JWT secret key.

    Requirements:
    - Must be at least 32 characters
    - Must not be a default/placeholder value
    - Should contain mixed characters for entropy

    Args:
        secret: The JWT secret key

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not secret:
        return False, "JWT_SECRET_KEY is not set"

    # Check for default/placeholder values
    forbidden_values = [
        "CHANGE_ME",
        "changeme",
        "secret",
        "your-secret-key",
        "jwt-secret",
        "supersecret",
        "development",
        "test",
    ]

    if secret.lower() in [v.lower() for v in forbidden_values]:
        return False, f"JWT_SECRET_KEY cannot be a default value like '{secret}'"

    # Check minimum length
    if len(secret) < 32:
        return False, f"JWT_SECRET_KEY must be at least 32 characters (got {len(secret)})"

    # Check for some entropy (mix of character types)
    has_upper = bool(re.search(r"[A-Z]", secret))
    has_lower = bool(re.search(r"[a-z]", secret))
    has_digit = bool(re.search(r"\d", secret))

    if not (has_upper or has_lower) and not has_digit:
        return False, "JWT_SECRET_KEY should contain a mix of letters and numbers"

    return True, None


def validate_encryption_key(key: str | None) -> tuple[bool, str | None]:
    """
    Validate encryption key for token storage.

    Requirements:
    - Must be set if token encryption is enabled
    - Must be a valid Fernet key (44 characters, base64)

    Args:
        key: The encryption key

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not key:
        return False, "TOKEN_ENCRYPTION_KEY is not set"

    # Fernet keys are 44 characters (32 bytes base64-encoded + padding)
    if len(key) != 44:
        return False, f"TOKEN_ENCRYPTION_KEY must be 44 characters (got {len(key)})"

    # Check if it's valid base64
    try:
        import base64

        decoded = base64.urlsafe_b64decode(key)
        if len(decoded) != 32:
            return False, "TOKEN_ENCRYPTION_KEY is not a valid Fernet key"
    except Exception:
        return False, "TOKEN_ENCRYPTION_KEY is not valid base64"

    return True, None


def validate_cors_origins(origins: str) -> tuple[bool, str | None, str | None]:
    """
    Validate CORS allowed origins.

    Args:
        origins: Comma-separated list of origins

    Returns:
        Tuple of (is_valid, error_message, warning_message)
    """
    if not origins:
        return False, "CORS_ALLOWED_ORIGINS is not set", None

    origin_list = [o.strip() for o in origins.split(",")]

    # Check for wildcard in production
    if "*" in origin_list:
        return True, None, "CORS allows all origins (*) - not recommended for production"

    # Check for localhost in production
    localhost_patterns = ["localhost", "127.0.0.1", "0.0.0.0"]
    has_localhost = any(
        any(pattern in origin for pattern in localhost_patterns) for origin in origin_list
    )

    if has_localhost and os.getenv("ENV") == "production":
        return (
            True,
            None,
            "CORS includes localhost origins - verify this is intentional in production",
        )

    return True, None, None


def validate_database_url(url: str) -> tuple[bool, str | None, str | None]:
    """
    Validate database URL security.

    Args:
        url: Database connection URL

    Returns:
        Tuple of (is_valid, error_message, warning_message)
    """
    if not url:
        return False, "DATABASE_URL is not set", None

    # Check for SQLite in production
    if url.startswith("sqlite") and os.getenv("ENV") == "production":
        return True, None, "Using SQLite in production - consider PostgreSQL for better performance"

    # Check for credentials in URL
    if "@" in url and "://" in url:
        # URL contains credentials
        parts = url.split("://")[1].split("@")[0]
        if ":" in parts:
            username, password = parts.split(":", 1)
            if password in ["password", "postgres", "admin", "root", ""]:
                return True, None, "Database password appears to be weak or default"

    return True, None, None


def validate_security_config(
    jwt_secret: str,
    encryption_key: str | None = None,
    cors_origins: str | None = None,
    database_url: str | None = None,
    require_encryption: bool = True,
    strict: bool = False,
) -> ValidationResult:
    """
    Validate all security configuration.

    Args:
        jwt_secret: JWT secret key
        encryption_key: Token encryption key
        cors_origins: CORS allowed origins
        database_url: Database connection URL
        require_encryption: Whether encryption key is required
        strict: If True, treat warnings as errors

    Returns:
        ValidationResult with errors and warnings

    Raises:
        SecurityConfigError: If strict=True and validation fails
    """
    errors = []
    warnings = []

    # Validate JWT secret (always required)
    valid, error = validate_jwt_secret(jwt_secret)
    if not valid:
        errors.append(error)

    # Validate encryption key
    if require_encryption:
        valid, error = validate_encryption_key(encryption_key)
        if not valid:
            errors.append(error)
    elif encryption_key:
        valid, error = validate_encryption_key(encryption_key)
        if not valid:
            warnings.append(f"Invalid encryption key: {error}")

    # Validate CORS
    if cors_origins:
        valid, error, warning = validate_cors_origins(cors_origins)
        if not valid:
            errors.append(error)
        if warning:
            warnings.append(warning)

    # Validate database
    if database_url:
        valid, error, warning = validate_database_url(database_url)
        if not valid:
            errors.append(error)
        if warning:
            warnings.append(warning)

    # Filter out None values
    errors_filtered = [e for e in errors if e is not None]
    warnings_filtered = [w for w in warnings if w is not None]

    # Log results
    if errors_filtered:
        for error in errors_filtered:
            logger.error("config_validation_error", error=error)

    if warnings_filtered:
        for warning in warnings_filtered:
            logger.warning("config_validation_warning", warning=warning)

    result = ValidationResult(
        valid=len(errors_filtered) == 0,
        errors=errors_filtered,
        warnings=warnings_filtered,
    )

    if strict and (errors_filtered or warnings_filtered):
        raise SecurityConfigError(errors_filtered + warnings_filtered)
    elif errors_filtered:
        raise SecurityConfigError(errors_filtered)

    return result


def generate_secure_key(key_type: str = "jwt") -> str:
    """
    Generate a secure random key.

    Args:
        key_type: Type of key to generate ("jwt" or "fernet")

    Returns:
        Secure random key string
    """
    import base64
    import secrets

    if key_type == "fernet":
        # Fernet requires exactly 32 bytes, base64-encoded
        key = secrets.token_bytes(32)
        return base64.urlsafe_b64encode(key).decode()
    else:
        # JWT secret - 64 random characters
        return secrets.token_urlsafe(48)


def print_key_generation_help():
    """Print help for generating secure keys."""
    print("\n" + "=" * 60)
    print("SECURITY KEY GENERATION HELP")
    print("=" * 60)
    print("\nGenerate secure keys with these commands:\n")
    print("# JWT Secret (for JWT_SECRET_KEY):")
    print('python -c "import secrets; print(secrets.token_urlsafe(48))"')
    print()
    print("# Fernet Key (for TOKEN_ENCRYPTION_KEY):")
    print(
        'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
    )
    print()
    print("Add these to your .env file:")
    print("  JWT_SECRET_KEY=<generated_jwt_secret>")
    print("  TOKEN_ENCRYPTION_KEY=<generated_fernet_key>")
    print("=" * 60 + "\n")
