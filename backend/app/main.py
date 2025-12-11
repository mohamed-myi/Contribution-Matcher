"""
FastAPI application entry point.

Uses structured logging from core.logging module.
Includes security validation and rate limiting.
"""

import time
from typing import Callable

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.logging import configure_logging, get_logger, RequestLoggingMiddleware
from core.db import db
from core.cache import cache
from core.security import (
    validate_security_config,
    SecurityConfigError,
    get_encryption_service,
    get_rate_limiter,
)

from .config import get_settings
from .dependencies.rate_limit import enforce_rate_limit
from .error_handlers import register_exception_handlers
from .middleware.request_id import RequestIDMiddleware
from .routers import auth as auth_router
from .routers import issues as issues_router
from .routers import jobs as jobs_router
from .routers import ml as ml_router
from .routers import profile as profile_router
from .routers import scoring as scoring_router
from .scheduler import shutdown_scheduler, start_scheduler


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size."""
    
    def __init__(self, app, max_size_mb: int = 10):
        super().__init__(app)
        self.max_size = max_size_mb * 1024 * 1024  # Convert to bytes
        self.max_size_mb = max_size_mb
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check Content-Length header if present
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_size:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "error": "Request too large",
                            "detail": f"Maximum request size is {self.max_size_mb}MB",
                        },
                    )
            except ValueError:
                pass
        
        return await call_next(request)


# Configure structured logging
settings = get_settings()
log_level = "DEBUG" if settings.debug else "INFO"
configure_logging(level=log_level)
logger = get_logger("api")


def validate_security_on_startup():
    """Validate security configuration before starting the app."""
    try:
        result = validate_security_config(
            jwt_secret=settings.jwt_secret_key,
            encryption_key=settings.token_encryption_key,
            cors_origins=settings.cors_allowed_origins,
            database_url=settings.database_url,
            require_encryption=settings.require_encryption,
            strict=settings.strict_security,
        )
        
        if result.warnings:
            for warning in result.warnings:
                logger.warning("security_warning", message=warning)
        
        # Also check production config warnings
        config_errors, config_warnings = settings.validate_production_config()
        for warning in config_warnings:
            logger.warning("config_warning", message=warning)
        
        logger.info("security_validation_passed")
        return True
        
    except SecurityConfigError as e:
        for error in e.errors:
            logger.error("security_config_error", error=error)
        
        if settings.debug:
            # In debug mode, log instructions for generating keys
            from core.security.validation import print_key_generation_help
            print_key_generation_help()
        
        raise


def check_database_health(max_retries: int = 3, retry_delay: float = 2.0) -> bool:
    """
    Check database connectivity with retry logic.
    
    Args:
        max_retries: Maximum number of connection attempts
        retry_delay: Seconds to wait between retries
        
    Returns:
        True if database is reachable
        
    Raises:
        RuntimeError: If database is unreachable after all retries
    """
    from sqlalchemy import text
    
    for attempt in range(max_retries):
        try:
            # Use a simple query to test connectivity
            with db.get_session() as session:
                session.execute(text("SELECT 1"))
            logger.info("database_health_check_passed", attempt=attempt + 1)
            return True
        except Exception as e:
            logger.warning(
                "database_health_check_failed",
                attempt=attempt + 1,
                max_retries=max_retries,
                error=str(e),
            )
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
    
    raise RuntimeError(
        f"Database unreachable after {max_retries} attempts. "
        "Check DATABASE_URL configuration and database server status."
    )


def create_app() -> FastAPI:
    import os
    
    # API version prefix
    api_version = "v1"
    api_prefix = f"{settings.api_prefix}/{api_version}"
    
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    # Request size limit middleware (configurable via MAX_REQUEST_SIZE_MB)
    app.add_middleware(RequestSizeLimitMiddleware, max_size_mb=settings.max_request_size_mb)
    
    # Trusted host middleware (only in production)
    env = os.getenv("ENV", "development").lower()
    is_production = env in ("production", "prod")
    if is_production:
        # Parse allowed hosts from CORS origins
        allowed_hosts = []
        for origin in settings.cors_allowed_origins.split(","):
            origin = origin.strip()
            # Extract hostname from URL
            if "://" in origin:
                host = origin.split("://")[1].split("/")[0].split(":")[0]
                allowed_hosts.append(host)
        
        if allowed_hosts:
            app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    
    # CORS middleware - restricted to specific methods and headers for security
    origins = [origin.strip() for origin in settings.cors_allowed_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        # Only allow methods actually used by the API
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        # Only allow headers needed for API communication
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Accept-Encoding",
            "Origin",
            "X-Requested-With",
            "X-CSRF-Token",
        ],
        # Expose rate limit headers to frontend
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Retry-After",
        ],
    )
    
    # GZip compression for responses > 500 bytes
    app.add_middleware(GZipMiddleware, minimum_size=500)
    
    # Request ID middleware (for tracing)
    app.add_middleware(RequestIDMiddleware)
    
    # Structured request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Exception handlers
    register_exception_handlers(app)

    @app.on_event("startup")
    async def startup_event():
        """Initialize services on startup."""
        import os
        
        logger.info("app_startup", app_name=settings.app_name)
        
        # Determine if we're in a safe environment for bypassing security checks
        # Both debug flag AND non-production ENV required to skip security validation
        env = os.getenv("ENV", "development").lower()
        is_production = env in ("production", "prod")
        allow_security_bypass = settings.debug and not is_production
        
        # Validate security configuration
        try:
            validate_security_on_startup()
        except SecurityConfigError:
            if not allow_security_bypass:
                # In production or non-debug mode, security errors are fatal
                logger.error(
                    "security_validation_failed_fatal",
                    message="Security validation failed. Set valid secrets or use ENV=development with DEBUG=true to bypass.",
                )
                raise
            logger.warning(
                "security_validation_skipped",
                message="Security validation bypassed (DEBUG=true and ENV!=production)",
            )
        
        # Initialize database
        db.initialize(settings.database_url)
        logger.info("database_initialized")
        
        # Verify database connectivity with retry
        check_database_health(max_retries=3, retry_delay=2.0)
        
        # Initialize cache
        cache.initialize()
        if cache.is_available:
            logger.info("cache_initialized", redis_host=settings.redis_host)
        else:
            logger.warning("cache_unavailable")
        
        # Initialize encryption service
        encryption = get_encryption_service()
        if encryption.is_available:
            logger.info("encryption_initialized")
        else:
            if settings.require_encryption:
                raise RuntimeError("Encryption required but not available")
            logger.warning("encryption_unavailable")
        
        # Initialize rate limiter
        limiter = get_rate_limiter()
        if limiter.is_available:
            logger.info("rate_limiter_initialized")
        else:
            logger.warning("rate_limiter_unavailable")
        
        # Start scheduler if enabled
        if settings.enable_scheduler:
            start_scheduler()
            logger.info("scheduler_started")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown."""
        logger.info("app_shutdown")
        
        if settings.enable_scheduler:
            shutdown_scheduler()
            logger.info("scheduler_stopped")

    @app.get("/health", tags=["health"])
    def health_check():
        """
        Health check endpoint (liveness probe).
        
        Returns minimal information to avoid exposing infrastructure details.
        Use /health/ready for readiness checks, /health/detailed for debug info.
        """
        # Only return basic status - no infrastructure details
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    def readiness_check():
        """
        Readiness check endpoint.
        
        Verifies that critical services (database, cache) are operational.
        Used by load balancers and container orchestrators.
        
        Returns 200 if ready, 503 if not ready.
        """
        from sqlalchemy import text
        
        checks = {
            "database": False,
            "cache": False,
        }
        all_ready = True
        
        # Check database
        try:
            if db.is_initialized:
                with db.get_session() as session:
                    session.execute(text("SELECT 1"))
                checks["database"] = True
            else:
                all_ready = False
        except Exception:
            all_ready = False
        
        # Check cache (Redis)
        try:
            if cache.is_available:
                cache.client.ping()
                checks["cache"] = True
            # Cache being unavailable is not fatal - it's optional
        except Exception:
            pass  # Cache failures are warnings, not errors
        
        if not checks["database"]:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "checks": checks},
            )
        
        return {"status": "ready", "checks": checks}

    @app.get("/health/detailed", tags=["health"])
    def health_check_detailed():
        """
        Detailed health check with infrastructure status.
        
        Only available in debug mode to prevent information disclosure.
        """
        import os
        
        env = os.getenv("ENV", "development").lower()
        is_production = env in ("production", "prod")
        
        # Block detailed health info in production
        if is_production or not settings.debug:
            return {"error": "Detailed health info only available in debug mode"}
        
        return {
            "status": "ok",
            "cache": cache.health_check() if cache.is_available else {"status": "unavailable"},
            "encryption": "available" if get_encryption_service().is_available else "unavailable",
            "rate_limiter": "available" if get_rate_limiter().is_available else "unavailable",
        }

    @app.get("/security/status", tags=["health"])
    def security_status():
        """
        Security service status.
        
        Only available in debug mode AND non-production to prevent information disclosure.
        """
        import os
        
        env = os.getenv("ENV", "development").lower()
        is_production = env in ("production", "prod")
        
        if is_production or not settings.debug:
            return {"error": "Security status only available in debug mode"}
        
        return {
            "jwt_configured": settings.jwt_secret_key != "CHANGE_ME",
            "encryption_available": get_encryption_service().is_available,
            "rate_limiter_available": get_rate_limiter().is_available,
            "strict_security": settings.strict_security,
            "require_encryption": settings.require_encryption,
        }

    # Protected route dependencies
    protected_dependencies = [Depends(enforce_rate_limit)]

    # Register routers with versioned API prefix
    # API is accessible at /api/v1/*
    app.include_router(auth_router.router, prefix=api_prefix)
    app.include_router(
        issues_router.router,
        prefix=api_prefix,
        dependencies=protected_dependencies,
    )
    app.include_router(
        profile_router.router,
        prefix=api_prefix,
        dependencies=protected_dependencies,
    )
    app.include_router(
        scoring_router.router,
        prefix=api_prefix,
        dependencies=protected_dependencies,
    )
    app.include_router(
        ml_router.router,
        prefix=api_prefix,
        dependencies=protected_dependencies,
    )
    app.include_router(
        jobs_router.router,
        prefix=api_prefix,
        dependencies=protected_dependencies,
    )

    return app


app = create_app()
