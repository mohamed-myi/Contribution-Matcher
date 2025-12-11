# =============================================================================
# Contribution Matcher - Multi-stage Dockerfile
# =============================================================================
# Supports multiple targets:
#   - api: FastAPI application (uvicorn)
#   - worker: Celery worker
#   - scheduler: Celery beat scheduler
#   - cli: CLI tools
#
# Build examples:
#   docker build --target api -t contribution-matcher-api .
#   docker build --target worker -t contribution-matcher-worker .
#   docker build --target scheduler -t contribution-matcher-scheduler .
# =============================================================================

# =============================================================================
# Base stage - Common dependencies
# =============================================================================
FROM python:3.11-slim AS base

# Prevent Python from writing bytecode and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# =============================================================================
# Dependencies stage - Install Python packages
# =============================================================================
FROM base AS dependencies

# Copy requirements first for better caching
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install additional production dependencies
RUN pip install --no-cache-dir \
    gunicorn \
    psycopg2-binary \
    redis \
    celery[redis] \
    cryptography

# =============================================================================
# Application stage - Copy source code
# =============================================================================
FROM dependencies AS app

# Copy application code
COPY core/ ./core/
COPY backend/ ./backend/
COPY workers/ ./workers/
COPY main.py ./

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app

# =============================================================================
# API Service
# =============================================================================
FROM app AS api

USER appuser

# Health check - uses /health/ready to verify DB and Redis connectivity
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/ready || exit 1

EXPOSE 8000

# Run with gunicorn for production
CMD ["gunicorn", "backend.app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]

# =============================================================================
# Celery Worker - Discovery Queue
# =============================================================================
FROM app AS worker-discovery

USER appuser

# Discovery worker - rate limited for GitHub API
CMD ["celery", "-A", "workers.celery_app", "worker", \
     "--queues=discovery", \
     "--concurrency=2", \
     "--loglevel=INFO", \
     "--max-tasks-per-child=100"]

# =============================================================================
# Celery Worker - Scoring Queue
# =============================================================================
FROM app AS worker-scoring

USER appuser

# Scoring worker - CPU intensive, more workers
CMD ["celery", "-A", "workers.celery_app", "worker", \
     "--queues=scoring", \
     "--concurrency=4", \
     "--loglevel=INFO", \
     "--max-tasks-per-child=500"]

# =============================================================================
# Celery Worker - ML Queue
# =============================================================================
FROM app AS worker-ml

USER appuser

# ML worker - Memory intensive, single worker
CMD ["celery", "-A", "workers.celery_app", "worker", \
     "--queues=ml", \
     "--concurrency=1", \
     "--loglevel=INFO", \
     "--max-tasks-per-child=10"]

# =============================================================================
# Celery Worker - Default (all queues)
# =============================================================================
FROM app AS worker

USER appuser

CMD ["celery", "-A", "workers.celery_app", "worker", \
     "--queues=default,discovery,scoring,ml", \
     "--concurrency=2", \
     "--loglevel=INFO", \
     "--max-tasks-per-child=100"]

# =============================================================================
# Celery Beat Scheduler
# =============================================================================
FROM app AS scheduler

USER appuser

CMD ["celery", "-A", "workers.celery_app", "beat", \
     "--loglevel=INFO"]

# =============================================================================
# CLI Tools
# =============================================================================
FROM app AS cli

USER appuser

ENTRYPOINT ["python", "main.py"]
CMD ["--help"]

