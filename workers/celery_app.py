"""
Celery application configuration.

Configures Celery with:
- Redis as broker and result backend
- Task routing to specialized queues
- Rate limiting for GitHub API calls
- Retry policies for transient failures
"""

from celery import Celery
from celery.signals import worker_process_init
from kombu import Exchange, Queue

from core.config import get_settings
from workers.schedules import apply_beat_schedule

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
# Queue Configuration with Priority Support
# =============================================================================

# Define exchanges
default_exchange = Exchange("default", type="direct")
discovery_exchange = Exchange("discovery", type="direct")
scoring_exchange = Exchange("scoring", type="direct")
ml_exchange = Exchange("ml", type="direct")
staleness_exchange = Exchange("staleness", type="direct")

# Define queues with priority support
# Priority: 0 (highest) to 9 (lowest), default is 4
# Use 'x-max-priority' to enable priority queue in RabbitMQ/Redis
celery_app.conf.task_queues = (
    Queue(
        "default",
        default_exchange,
        routing_key="default",
        queue_arguments={"x-max-priority": 10},
    ),
    Queue(
        "scoring",
        scoring_exchange,
        routing_key="scoring",
        queue_arguments={"x-max-priority": 10},
    ),
    Queue(
        "discovery",
        discovery_exchange,
        routing_key="discovery",
        queue_arguments={"x-max-priority": 10},
    ),
    Queue(
        "ml",
        ml_exchange,
        routing_key="ml",
        queue_arguments={"x-max-priority": 10},
    ),
    Queue(
        "staleness",
        staleness_exchange,
        routing_key="staleness",
        queue_arguments={"x-max-priority": 10},
    ),
)

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "default"
celery_app.conf.task_default_routing_key = "default"

# Default task priority (0=highest, 9=lowest)
celery_app.conf.task_default_priority = 5

# =============================================================================
# Task Routing with Priority
# =============================================================================

celery_app.conf.task_routes = {
    # Scoring tasks -> scoring queue (high priority)
    # Priority 2: Fast response needed for API requests
    "workers.tasks.scoring_tasks.*": {
        "queue": "scoring",
        "routing_key": "scoring",
        "priority": 2,
    },
    # Discovery tasks -> discovery queue (medium priority)
    # Priority 5: Background discovery
    "workers.tasks.discovery_tasks.*": {
        "queue": "discovery",
        "routing_key": "discovery",
        "priority": 5,
    },
    # ML tasks -> ml queue (medium-low priority)
    # Priority 6: Resource intensive, can wait
    "workers.tasks.ml_tasks.*": {
        "queue": "ml",
        "routing_key": "ml",
        "priority": 6,
    },
    # Staleness tasks -> staleness queue (low priority)
    # Priority 8: Background cleanup, lowest priority
    "workers.tasks.staleness_tasks.*": {
        "queue": "staleness",
        "routing_key": "staleness",
        "priority": 8,
    },
}

# =============================================================================
# Worker Concurrency Configuration
# =============================================================================

# Configure concurrency per queue type when running workers:
# celery -A workers worker -Q scoring -c 8 --prefetch-multiplier=4
# celery -A workers worker -Q discovery -c 2 --prefetch-multiplier=1
# celery -A workers worker -Q ml -c 1 --prefetch-multiplier=1
# celery -A workers worker -Q staleness -c 2 --prefetch-multiplier=1

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
    task_time_limit=600,  # 10 minutes hard limit
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


@worker_process_init.connect
def setup_worker_logging(**kwargs):
    """Configure structured logging when worker starts."""
    from core.logging import configure_celery_logging, configure_logging

    configure_logging(level="INFO")
    configure_celery_logging()


# =============================================================================
# Beat Schedule (Periodic Tasks)
# =============================================================================


apply_beat_schedule(celery_app)


# =============================================================================
# Auto-discovery (optional - we explicitly include tasks above)
# =============================================================================

# Uncomment to auto-discover tasks in Django apps
# celery_app.autodiscover_tasks()
