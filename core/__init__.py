"""
Contribution Matcher Core Library.

This package provides the core functionality for the Contribution Matcher,
including database management, models, repositories, services, and logging.

Usage:
    # Database
    from core.database import db, get_db
    from core.models import User, Issue, DevProfile
    from core.repositories import IssueRepository, UserRepository
    
    # Config
    from core.config import get_settings, Settings
    
    # Logging
    from core.logging import get_logger, configure_logging

Note: This package was renamed from 'contribution_matcher' to 'core'.
"""

__version__ = "1.0.0"

# Lazy imports to avoid circular dependencies
# Users should import directly from submodules:
#   from core.database import db
#   from core.config import get_settings
#   from core.logging import get_logger

