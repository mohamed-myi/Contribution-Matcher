"""
API Application Factory.

Creates and configures the FastAPI application with:
- Domain routers
- Middleware
- Exception handlers
- Health checks
"""

import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from packages.api.src.domains.auth import auth_router
from packages.api.src.domains.issues import issues_router
from packages.api.src.domains.profiles import profiles_router
from packages.api.src.domains.scoring import scoring_router
from packages.api.src.domains.ml import ml_router
from packages.api.src.infrastructure.database import db
from packages.api.src.infrastructure.cache import cache
from packages.shared.types import HealthResponse

# Track startup time
_startup_time: float = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global _startup_time
    _startup_time = time.time()
    
    # Initialize database
    from core.config import get_settings
    settings = get_settings()
    db.initialize(settings.database_url)
    
    # Initialize cache
    cache.initialize()
    
    yield
    
    # Cleanup
    db.reset()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="Contribution Matcher API",
        description="Match developers with open source contribution opportunities",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        import uuid
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": str(exc) if app.debug else "An unexpected error occurred",
            },
        )
    
    # Health check endpoint
    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health_check():
        """Check service health."""
        db_health = db.health_check()
        cache_health = cache.health_check()
        
        uptime = time.time() - _startup_time if _startup_time else 0
        
        status = "healthy"
        if not db_health.get("healthy"):
            status = "unhealthy"
        elif not cache_health.get("available"):
            status = "degraded"
        
        return {
            "status": status,
            "version": "1.0.0",
            "database": db_health,
            "cache": cache_health,
            "uptime_seconds": round(uptime, 2),
        }
    
    # Root endpoint
    @app.get("/", tags=["root"])
    async def root():
        """API root endpoint."""
        return {
            "name": "Contribution Matcher API",
            "version": "1.0.0",
            "docs": "/docs",
        }
    
    # Register domain routers
    app.include_router(auth_router)
    app.include_router(issues_router)
    app.include_router(profiles_router)
    app.include_router(scoring_router)
    app.include_router(ml_router)
    
    return app


# Create default app instance
app = create_app()
