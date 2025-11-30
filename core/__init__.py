"""
Contribution Matcher Core Library.

Provides database management, models, repositories, services, and logging.

Usage:
    from core.database import db, get_db
    from core.models import User, Issue, DevProfile
    from core.config import get_settings
    from core.logging import get_logger
"""

__version__ = "1.0.0"

# Lazy imports to avoid circular dependencies
# Users should import directly from submodules:
#   from core.database import db
#   from core.config import get_settings
#   from core.logging import get_logger

