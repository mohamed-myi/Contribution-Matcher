"""
Application configuration using Pydantic settings.

This module provides backward compatibility with the existing backend code.
It re-exports from the unified core.config module.

For new code, prefer importing directly from core.config:
    from core.config import get_settings, Settings
"""

# Re-export from core.config for backward compatibility
from core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]

