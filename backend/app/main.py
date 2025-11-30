"""
FastAPI application entry point.

Uses structured logging from core.logging module.
Includes security validation and rate limiting.
"""

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    # CORS middleware
    origins = [origin.strip() for origin in settings.cors_allowed_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Request ID middleware (for tracing)
    app.add_middleware(RequestIDMiddleware)
    
    # Structured request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Exception handlers
    register_exception_handlers(app)

    @app.on_event("startup")
    async def startup_event():
        """Initialize services on startup."""
        logger.info("app_startup", app_name=settings.app_name)
        
        # Validate security configuration
        try:
            validate_security_on_startup()
        except SecurityConfigError:
            if not settings.debug:
                raise
            logger.warning("security_validation_skipped_debug_mode")
        
        # Initialize database
        db.initialize(settings.database_url)
        logger.info("database_initialized")
        
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
        """Health check endpoint."""
        return {
            "status": "ok",
            "cache": cache.health_check() if cache.is_available else {"status": "unavailable"},
            "encryption": "available" if get_encryption_service().is_available else "unavailable",
            "rate_limiter": "available" if get_rate_limiter().is_available else "unavailable",
        }

    @app.get("/security/status", tags=["health"])
    def security_status():
        """Get security service status (requires auth in production)."""
        if not settings.debug:
            return {"error": "Only available in debug mode"}
        
        return {
            "jwt_configured": settings.jwt_secret_key != "CHANGE_ME",
            "encryption_available": get_encryption_service().is_available,
            "rate_limiter_available": get_rate_limiter().is_available,
            "strict_security": settings.strict_security,
            "require_encryption": settings.require_encryption,
        }

    # Protected route dependencies
    protected_dependencies = [Depends(enforce_rate_limit)]

    # Register routers
    app.include_router(auth_router.router, prefix=settings.api_prefix)
    app.include_router(
        issues_router.router,
        prefix=settings.api_prefix,
        dependencies=protected_dependencies,
    )
    app.include_router(
        profile_router.router,
        prefix=settings.api_prefix,
        dependencies=protected_dependencies,
    )
    app.include_router(
        scoring_router.router,
        prefix=settings.api_prefix,
        dependencies=protected_dependencies,
    )
    app.include_router(
        ml_router.router,
        prefix=settings.api_prefix,
        dependencies=protected_dependencies,
    )
    app.include_router(
        jobs_router.router,
        prefix=settings.api_prefix,
        dependencies=protected_dependencies,
    )

    return app


app = create_app()
