"""
Custom exception handlers for FastAPI.

Security:
- Request IDs are logged server-side for tracing but NOT exposed to clients
- Generic error messages for 500 errors to prevent information disclosure
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from core.logging import get_logger
import structlog

logger = get_logger("backend.errors")


def _get_request_id() -> str:
    """
    Get the current request ID from context.
    
    Used for server-side logging only - NOT exposed to clients.
    """
    try:
        ctx = structlog.contextvars.get_contextvars()
        return ctx.get("request_id", "-")
    except Exception:
        return "-"


def _response_payload(detail: str, status_code: int) -> dict:
    """
    Create error response payload.
    
    Security: Does NOT include request_id to prevent information disclosure.
    Request IDs are still logged server-side for debugging.
    """
    return {
        "detail": detail,
        "status_code": status_code,
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        # Log with request_id for server-side tracing
        request_id = _get_request_id()
        logger.warning(
            "http_exception",
            detail=exc.detail,
            status_code=exc.status_code,
            request_id=request_id,
        )
        # Response does NOT include request_id
        return JSONResponse(
            status_code=exc.status_code,
            content=_response_payload(str(exc.detail), exc.status_code),
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        request_id = _get_request_id()
        logger.warning(
            "validation_error",
            errors=exc.errors(),
            request_id=request_id,
        )
        return JSONResponse(
            status_code=422,
            content={
                **_response_payload("Validation error", 422),
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        request_id = _get_request_id()
        # Log full details server-side (including request_id for tracing)
        logger.exception(
            "unhandled_exception",
            error=str(exc),
            error_type=type(exc).__name__,
            request_id=request_id,
        )
        # Return generic message - don't expose exception details
        return JSONResponse(
            status_code=500,
            content=_response_payload("Internal server error", 500),
        )
