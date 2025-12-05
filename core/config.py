"""
Application configuration using Pydantic settings.

Usage:
    from core.config import get_settings
    settings = get_settings()

For constants, import from core.constants:
    from core.constants import SKILL_CATEGORIES, DISCOVERY_LABELS
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Unified application settings loaded from environment variables and .env file.
    
    Required for production:
        - JWT_SECRET_KEY (min 32 chars)
        - GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET (for OAuth)
        - PAT_TOKEN (for GitHub API)
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App settings
    app_name: str = "Contribution Matcher"
    api_prefix: str = "/api"
    debug: bool = Field(default=False)

    # Database
    database_url: str = Field(default="sqlite:///contribution_matcher.db", validation_alias="DATABASE_URL")
    db_pool_size: int = Field(default=10, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, validation_alias="DB_MAX_OVERFLOW")
    db_pool_pre_ping: bool = Field(default=True, validation_alias="DB_POOL_PRE_PING")

    # GitHub OAuth
    github_client_id: str = Field(default="", validation_alias="GITHUB_CLIENT_ID")
    github_client_secret: str = Field(default="", validation_alias="GITHUB_CLIENT_SECRET")
    github_redirect_uri: Optional[AnyHttpUrl] = Field(default=None, validation_alias="GITHUB_REDIRECT_URI")
    github_scope: str = Field(default="read:user user:email")
    pat_token: Optional[str] = Field(default=None, validation_alias="PAT_TOKEN")

    # JWT / Authentication
    jwt_secret_key: str = Field(default="CHANGE_ME", validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60 * 24)
    
    # Token encryption (STRONGLY RECOMMENDED for production)
    # GitHub access tokens are encrypted at rest when this key is set
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    token_encryption_key: Optional[str] = Field(default=None, validation_alias="TOKEN_ENCRYPTION_KEY")
    require_encryption: bool = Field(default=False, validation_alias="REQUIRE_ENCRYPTION")
    strict_security: bool = Field(default=False, validation_alias="STRICT_SECURITY")
    
    # Rate limiting
    auth_rate_limit: int = Field(default=5, validation_alias="AUTH_RATE_LIMIT")
    auth_rate_window: int = Field(default=300, validation_alias="AUTH_RATE_WINDOW")
    api_rate_limit: int = Field(default=100, validation_alias="API_RATE_LIMIT")
    api_rate_window: int = Field(default=60, validation_alias="API_RATE_WINDOW")

    # CORS
    cors_allowed_origins: str = Field(default="http://localhost:5173", validation_alias="CORS_ALLOWED_ORIGINS")

    # Redis
    redis_host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="REDIS_PORT")
    redis_db: int = Field(default=0, validation_alias="REDIS_DB")
    redis_password: Optional[str] = Field(default=None, validation_alias="REDIS_PASSWORD")
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL from components."""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Celery
    celery_broker_url: str = Field(default="redis://localhost:6379/1", validation_alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/2", validation_alias="CELERY_RESULT_BACKEND")

    # Scheduler
    enable_scheduler: bool = Field(default=False, validation_alias="ENABLE_SCHEDULER")
    scheduler_discovery_cron: str = Field(default="0 6 * * *", validation_alias="SCHEDULER_DISCOVERY_CRON")
    scheduler_scoring_cron: str = Field(default="30 6 * * *", validation_alias="SCHEDULER_SCORING_CRON")
    scheduler_ml_cron: str = Field(default="0 7 * * *", validation_alias="SCHEDULER_ML_CRON")
    scheduler_discovery_limit: int = Field(default=50, validation_alias="SCHEDULER_DISCOVERY_LIMIT")
    
    # Discovery
    fast_discovery: bool = Field(default=True, validation_alias="FAST_DISCOVERY")
    cache_validity_days: int = Field(default=7, validation_alias="CACHE_VALIDITY_DAYS")

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate JWT secret - warns in dev, errors in production."""
        import os
            import warnings
        
        env = os.getenv("ENV", "development")
        is_production = env.lower() in ("production", "prod")
        
        # List of forbidden default/weak values
        forbidden_values = [
            "CHANGE_ME", "changeme", "secret", "your-secret-key",
            "jwt-secret", "supersecret", "development", "test",
        ]
        
        is_forbidden = v.lower() in [fv.lower() for fv in forbidden_values]
        is_too_short = len(v) < 32
        
        if is_production:
            # In production, fail hard on insecure secrets
            if is_forbidden:
                raise ValueError(
                    f"JWT_SECRET_KEY cannot be a default value ('{v}') in production. "
                    "Generate a secure key with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )
            if is_too_short:
                raise ValueError(
                    f"JWT_SECRET_KEY must be at least 32 characters in production (got {len(v)}). "
                    "Generate a secure key with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )
        else:
            # In development, warn but allow
            if is_forbidden:
            warnings.warn(
                    f"JWT_SECRET_KEY is set to a default value ('{v}'). "
                    "This is insecure - set a proper key for production.",
                UserWarning,
                stacklevel=2
            )
            elif is_too_short:
            warnings.warn(
                f"JWT_SECRET_KEY should be at least 32 characters (got {len(v)})",
                UserWarning,
                stacklevel=2
            )
        
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    def validate_production_config(self) -> tuple[List[str], List[str]]:
        """
        Validate configuration for production deployment.
        
        Returns:
            Tuple of (errors, warnings) - errors are fatal, warnings are advisory
        """
        errors = []
        warnings = []
        
        if self.jwt_secret_key == "CHANGE_ME":
            errors.append("JWT_SECRET_KEY must be set for production")
        elif len(self.jwt_secret_key) < 32:
            errors.append("JWT_SECRET_KEY must be at least 32 characters")
        
        if not self.github_client_id:
            errors.append("GITHUB_CLIENT_ID is required for OAuth")
        if not self.github_client_secret:
            errors.append("GITHUB_CLIENT_SECRET is required for OAuth")
        if not self.pat_token:
            errors.append("PAT_TOKEN is required for GitHub API access")
        
        # Token encryption warning (strongly recommended)
        if not self.token_encryption_key:
            warnings.append(
                "TOKEN_ENCRYPTION_KEY not set - GitHub access tokens will be stored "
                "in plaintext. Set this key to encrypt tokens at rest."
            )
        
        if self.strict_security:
            if not self.token_encryption_key:
                errors.append("TOKEN_ENCRYPTION_KEY required when STRICT_SECURITY=true")
            if "localhost" in self.cors_allowed_origins:
                errors.append("CORS should not allow localhost in strict security mode")
        
        return errors, warnings


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


__all__ = ["Settings", "get_settings"]
