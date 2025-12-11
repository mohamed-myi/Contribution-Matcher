"""Structured logging configuration for Contribution Matcher."""

import logging
import os
import sys
import time
from collections.abc import Callable, Mapping, MutableMapping
from functools import lru_cache, wraps
from typing import Any, TypeVar

import structlog
from structlog.types import Processor

F = TypeVar("F", bound=Callable[..., Any])


def _is_development() -> bool:
    """Check if running in development mode."""
    from .config import get_settings

    settings = get_settings()
    return settings.debug or os.getenv("ENV", "development") == "development"


def _add_app_context(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any] | str | bytes | bytearray | tuple[Any, ...]:
    """Add application context to log entries."""
    event_dict["app"] = "contribution_matcher"
    return event_dict


def get_processors() -> list[Processor]:
    """Get structlog processors based on environment."""
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
    return shared_processors + [
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]


@lru_cache(maxsize=1)
def configure_logging(level: str = "INFO") -> None:
    """Configure structured logging. Call once at application startup."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=get_processors(),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    if not structlog.is_configured():
        configure_logging()
    return structlog.get_logger(name)  # type: ignore[no-any-return]


# =============================================================================
# Context Management
# =============================================================================


def bind_context(**kwargs: Any) -> None:
    """Bind context variables included in all subsequent log entries."""
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
        structlog.contextvars.unbind_contextvars(*self._keys)
        return False


# =============================================================================
# Decorators
# =============================================================================


def log_function_call(logger: structlog.stdlib.BoundLogger | None = None) -> Callable[[F], F]:
    """
    Decorator to log function entry and exit.

    Usage:
        @log_function_call()
        def process_issue(issue_id: int):
            ...
    """

    def decorator(func: F) -> F:
        _logger = logger or get_logger(func.__module__)

        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            _logger.debug("function_entry", function=func_name, args_count=len(args))
            try:
                result = func(*args, **kwargs)
                _logger.debug("function_exit", function=func_name, success=True)
                return result
            except Exception as e:
                _logger.error(
                    "function_error", function=func_name, error=str(e), error_type=type(e).__name__
                )
                raise

        return wrapper  # type: ignore

    return decorator


def log_timing(
    operation: str, logger: structlog.stdlib.BoundLogger | None = None
) -> Callable[[F], F]:
    """
    Decorator to log function timing.

    Usage:
        @log_timing("issue_discovery")
        def discover_issues():
            ...
    """

    def decorator(func: F) -> F:
        _logger = logger or get_logger(func.__module__)

        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                _logger.info(
                    "operation_complete", operation=operation, duration_seconds=round(elapsed, 3)
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

        return wrapper  # type: ignore

    return decorator


# =============================================================================
# FastAPI Integration
# =============================================================================


class RequestLoggingMiddleware:
    """ASGI middleware for request logging."""

    def __init__(self, app):
        self.app = app
        self._logger: structlog.stdlib.BoundLogger | None = None

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Lazy-load logger to avoid import-time configuration issues."""
        if self._logger is None:
            self._logger = get_logger("http")
        return self._logger

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import uuid

        request_id = str(uuid.uuid4())[:8]
        start_time = time.perf_counter()

        bind_context(request_id=request_id)

        path = scope.get("path", "")
        method = scope.get("method", "")

        self.logger.info("request_started", method=method, path=path)

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
    """Configure structured logging for Celery workers."""
    from celery.signals import task_failure, task_postrun, task_prerun

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
        logger.error("task_failed", error=str(exception), error_type=type(exception).__name__)
        clear_context()


# =============================================================================
# Lazy-loaded Module Loggers
# =============================================================================


class _LazyLogger:
    """Lazy logger that defers initialization until first use."""

    def __init__(self, name: str):
        self._name = name
        self._logger: structlog.stdlib.BoundLogger | None = None

    def _get_logger(self) -> structlog.stdlib.BoundLogger:
        if self._logger is None:
            self._logger = get_logger(self._name)
        return self._logger

    def __getattr__(self, name: str):
        return getattr(self._get_logger(), name)


# Pre-configured loggers (lazy-loaded)
api_logger = _LazyLogger("api")
cli_logger = _LazyLogger("cli")
db_logger = _LazyLogger("database")
scoring_logger = _LazyLogger("scoring")
ml_logger = _LazyLogger("ml")
github_logger = _LazyLogger("github")
cache_logger = _LazyLogger("cache")
worker_logger = _LazyLogger("worker")


__all__ = [
    "configure_logging",
    "get_logger",
    "bind_context",
    "unbind_context",
    "clear_context",
    "LogContext",
    "log_function_call",
    "log_timing",
    "RequestLoggingMiddleware",
    "configure_celery_logging",
    "api_logger",
    "cli_logger",
    "db_logger",
    "scoring_logger",
    "ml_logger",
    "github_logger",
    "cache_logger",
    "worker_logger",
]
