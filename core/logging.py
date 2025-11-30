"""Structured logging configuration for Contribution Matcher."""

import logging
import sys
from functools import lru_cache
from typing import Any, Dict, Optional
import os

import structlog
from structlog.types import Processor

from .config import get_settings


def _is_development() -> bool:
    """Check if running in development mode."""
    settings = get_settings()
    return settings.debug or os.getenv("ENV", "development") == "development"


def _add_app_context(
    logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add application context to log entries."""
    event_dict["app"] = "contribution_matcher"
    return event_dict


def _add_caller_info(
    logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add caller module and function info (development only)."""
    if _is_development():
        # Get caller info from structlog's internal frame
        record = event_dict.get("_record")
        if record:
            event_dict["module"] = record.module
            event_dict["func"] = record.funcName
            event_dict["lineno"] = record.lineno
    return event_dict


def get_processors() -> list[Processor]:
    """Get the list of structlog processors based on environment."""
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _add_app_context,
    ]
    
    if _is_development():
        return shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            )
        ]
    else:
        return shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]


@lru_cache(maxsize=1)
def configure_logging(level: str = "INFO") -> None:
    """
    Configure structured logging for the application.
    
    Call this once at application startup.
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    
    # Configure structlog
    structlog.configure(
        processors=get_processors(),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    
    Usage:
        logger = get_logger(__name__)
        logger.info("processing_issue", issue_id=123, status="open")
    """
    # Ensure logging is configured
    if not structlog.is_configured():
        configure_logging()
    
    return structlog.get_logger(name)


# =============================================================================
# Context Management
# =============================================================================

def bind_context(**kwargs: Any) -> None:
    """
    Bind context variables that will be included in all subsequent log entries.
    
    Usage:
        bind_context(user_id=123, request_id="abc-123")
        logger.info("processing")  # Will include user_id and request_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """Remove context variables."""
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Clear all context variables."""
    structlog.contextvars.clear_contextvars()


class LogContext:
    """
    Context manager for temporary log context.
    
    Usage:
        with LogContext(user_id=123, operation="discover"):
            logger.info("starting")  # Includes user_id and operation
        logger.info("done")  # Does not include user_id or operation
    """
    
    def __init__(self, **kwargs: Any):
        self.kwargs = kwargs
        self._keys = list(kwargs.keys())
    
    def __enter__(self):
        structlog.contextvars.bind_contextvars(**self.kwargs)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Unbind the keys we added
        structlog.contextvars.unbind_contextvars(*self._keys)
        return False


# =============================================================================
# Decorators
# =============================================================================

def log_function_call(logger: Optional[structlog.stdlib.BoundLogger] = None):
    """
    Decorator to log function entry and exit.
    
    Usage:
        @log_function_call()
        def process_issue(issue_id: int):
            ...
    """
    def decorator(func):
        _logger = logger or get_logger(func.__module__)
        
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            _logger.debug("function_entry", function=func_name, args_count=len(args))
            try:
                result = func(*args, **kwargs)
                _logger.debug("function_exit", function=func_name, success=True)
                return result
            except Exception as e:
                _logger.error("function_error", function=func_name, error=str(e), error_type=type(e).__name__)
                raise
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator


def log_timing(operation: str, logger: Optional[structlog.stdlib.BoundLogger] = None):
    """
    Decorator to log function timing.
    
    Usage:
        @log_timing("issue_discovery")
        def discover_issues():
            ...
    """
    import time
    
    def decorator(func):
        _logger = logger or get_logger(func.__module__)
        
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                _logger.info(
                    "operation_complete",
                    operation=operation,
                    duration_seconds=round(elapsed, 3),
                )
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start
                _logger.error(
                    "operation_failed",
                    operation=operation,
                    duration_seconds=round(elapsed, 3),
                    error=str(e),
                )
                raise
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator


# =============================================================================
# FastAPI Integration
# =============================================================================

class RequestLoggingMiddleware:
    """
    ASGI middleware for request logging.
    
    Usage:
        from core.logging import RequestLoggingMiddleware
        app.add_middleware(RequestLoggingMiddleware)
    """
    
    def __init__(self, app):
        self.app = app
        self.logger = get_logger("http")
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import time
        import uuid
        
        request_id = str(uuid.uuid4())[:8]
        start_time = time.perf_counter()
        
        # Bind request context
        bind_context(request_id=request_id)
        
        # Extract request info
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        self.logger.info(
            "request_started",
            method=method,
            path=path,
        )
        
        # Track response status
        status_code = 500
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start_time
            
            log_method = self.logger.info if status_code < 400 else self.logger.warning
            if status_code >= 500:
                log_method = self.logger.error
            
            log_method(
                "request_complete",
                method=method,
                path=path,
                status_code=status_code,
                duration_seconds=round(duration, 3),
            )
            
            clear_context()


# =============================================================================
# Celery Integration
# =============================================================================

def configure_celery_logging():
    """
    Configure structured logging for Celery workers.
    
    Call this in Celery's worker_process_init signal.
    """
    from celery.signals import task_prerun, task_postrun, task_failure
    
    logger = get_logger("celery.tasks")
    
    @task_prerun.connect
    def task_prerun_handler(task_id, task, args, kwargs, **kw):
        bind_context(task_id=task_id, task_name=task.name)
        logger.info("task_started")
    
    @task_postrun.connect
    def task_postrun_handler(task_id, task, args, kwargs, retval, state, **kw):
        logger.info("task_completed", state=state)
        clear_context()
    
    @task_failure.connect
    def task_failure_handler(task_id, exception, args, kwargs, traceback, einfo, **kw):
        logger.error(
            "task_failed",
            error=str(exception),
            error_type=type(exception).__name__,
        )
        clear_context()


# =============================================================================
# Convenience Loggers
# =============================================================================

# Pre-configured loggers for common modules
api_logger = get_logger("api")
cli_logger = get_logger("cli")
db_logger = get_logger("database")
scoring_logger = get_logger("scoring")
ml_logger = get_logger("ml")
github_logger = get_logger("github")
cache_logger = get_logger("cache")
worker_logger = get_logger("worker")


# =============================================================================
# Migration Helper
# =============================================================================

def print_to_log(message: str, level: str = "info", **kwargs) -> None:
    """
    Helper for migrating from print() to structured logging.
    
    Usage (temporary during migration):
        # Instead of: print(f"Processing {count} issues")
        print_to_log("Processing issues", count=count)
    """
    logger = get_logger("migration")
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message, **kwargs)


__all__ = [
    # Configuration
    "configure_logging",
    "get_logger",
    # Context
    "bind_context",
    "unbind_context", 
    "clear_context",
    "LogContext",
    # Decorators
    "log_function_call",
    "log_timing",
    # Middleware
    "RequestLoggingMiddleware",
    # Celery
    "configure_celery_logging",
    # Pre-configured loggers
    "api_logger",
    "cli_logger",
    "db_logger",
    "scoring_logger",
    "ml_logger",
    "github_logger",
    "cache_logger",
    "worker_logger",
    # Migration
    "print_to_log",
]

