"""
Custom exception handlers for FastAPI.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from core.logging import get_logger
import structlog

logger = get_logger("backend.errors")


def _get_request_id() -> str:
    """Get the current request ID from context."""
    try:
        ctx = structlog.contextvars.get_contextvars()
        return ctx.get("request_id", "-")
    except Exception:
        return "-"


def _response_payload(detail: str, status_code: int) -> dict:
    return {
        "detail": detail,
        "status_code": status_code,
        "request_id": _get_request_id(),
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.warning("http_exception", detail=exc.detail, status_code=exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=_response_payload(str(exc.detail), exc.status_code),
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        logger.warning("validation_error", errors=exc.errors())
        return JSONResponse(
            status_code=422,
            content={
                **_response_payload("Validation error", 422),
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.exception("unhandled_exception", error=str(exc), error_type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=_response_payload("Internal server error", 500),
        )
