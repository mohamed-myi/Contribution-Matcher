"""
Celery application configuration.

Configures Celery with:
- Redis as broker and result backend
- Task routing to specialized queues
- Rate limiting for GitHub API calls
- Retry policies for transient failures
"""

from celery import Celery
from kombu import Exchange, Queue

from core.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "contribution_matcher",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "workers.tasks.discovery_tasks",
        "workers.tasks.scoring_tasks",
        "workers.tasks.ml_tasks",
    ],
)

# =============================================================================
# Queue Configuration
# =============================================================================

# Define exchanges
default_exchange = Exchange("default", type="direct")
discovery_exchange = Exchange("discovery", type="direct")
scoring_exchange = Exchange("scoring", type="direct")
ml_exchange = Exchange("ml", type="direct")

# Define queues
celery_app.conf.task_queues = (
    Queue("default", default_exchange, routing_key="default"),
    Queue("discovery", discovery_exchange, routing_key="discovery"),
    Queue("scoring", scoring_exchange, routing_key="scoring"),
    Queue("ml", ml_exchange, routing_key="ml"),
)

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "default"
celery_app.conf.task_default_routing_key = "default"

# =============================================================================
# Task Routing
# =============================================================================

celery_app.conf.task_routes = {
    # Discovery tasks -> discovery queue (rate limited)
    "workers.tasks.discovery_tasks.*": {
        "queue": "discovery",
        "routing_key": "discovery",
    },
    # Scoring tasks -> scoring queue (parallel)
    "workers.tasks.scoring_tasks.*": {
        "queue": "scoring",
        "routing_key": "scoring",
    },
    # ML tasks -> ml queue (resource intensive)
    "workers.tasks.ml_tasks.*": {
        "queue": "ml",
        "routing_key": "ml",
    },
}

# =============================================================================
# Serialization
# =============================================================================

celery_app.conf.update(
    # Use pickle for complex objects (ML models, numpy arrays)
    task_serializer="pickle",
    accept_content=["pickle", "json"],
    result_serializer="pickle",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
)

# =============================================================================
# Rate Limiting
# =============================================================================

celery_app.conf.update(
    # Default rate limit (can be overridden per-task)
    task_default_rate_limit=None,
    
    # Worker prefetch multiplier (how many tasks to prefetch)
    # Lower = more fair distribution, higher = better throughput
    worker_prefetch_multiplier=1,
)

# =============================================================================
# Retry Policy
# =============================================================================

celery_app.conf.update(
    # Retry on connection errors
    broker_connection_retry_on_startup=True,
    
    # Task result expiration (24 hours)
    result_expires=86400,
    
    # Task time limits
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_time_limit=600,       # 10 minutes hard limit
)

# =============================================================================
# Task Acknowledgment
# =============================================================================

celery_app.conf.update(
    # Acknowledge tasks after completion (not before)
    task_acks_late=True,
    
    # Reject tasks on worker shutdown (requeue them)
    task_reject_on_worker_lost=True,
)

# =============================================================================
# Logging
# =============================================================================

celery_app.conf.update(
    # Worker hijacks root logger
    worker_hijack_root_logger=False,
    
    # Task send sent event
    task_send_sent_event=True,
)

# Configure structured logging for Celery
from celery.signals import worker_process_init

@worker_process_init.connect
def setup_worker_logging(**kwargs):
    """Configure structured logging when worker starts."""
    from core.logging import configure_logging, configure_celery_logging
    configure_logging(level="INFO")
    configure_celery_logging()


# =============================================================================
# Beat Schedule (Periodic Tasks)
# =============================================================================

from workers.schedules import apply_beat_schedule
apply_beat_schedule(celery_app)


# =============================================================================
# Auto-discovery (optional - we explicitly include tasks above)
# =============================================================================

# Uncomment to auto-discover tasks in Django apps
# celery_app.autodiscover_tasks()

