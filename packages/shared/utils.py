"""
Shared Utilities.

Common utility functions used across all packages.
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeVar

T = TypeVar("T")


def normalize_tech_name(tech: str) -> str:
    """
    Normalize a technology name for consistent matching.
    
    Args:
        tech: Raw technology string.
    
    Returns:
        Normalized technology token.
    """
    return tech.lower().strip().replace(" ", "-").replace("_", "-")


def get_tech_variants(tech: str, synonyms: Dict[str, List[str]] = None) -> set:
    """
    Collect normalized variants and synonyms for a technology.
    
    Args:
        tech: Base technology string.
        synonyms: Optional synonym dictionary.
    
    Returns:
        Set of normalized technology variants.
    """
    from .constants import TECHNOLOGY_SYNONYMS
    
    synonyms = synonyms or TECHNOLOGY_SYNONYMS
    normalized = normalize_tech_name(tech)
    variants = {normalized}
    
    if normalized in synonyms:
        for synonym in synonyms[normalized]:
            variants.add(normalize_tech_name(synonym))
    
    return variants


def hash_string(value: str, algorithm: str = "sha256") -> str:
    """
    Create a hash of a string.
    
    Args:
        value: String to hash.
        algorithm: Hash algorithm (default: sha256).
    
    Returns:
        Hex digest of the hash.
    """
    h = hashlib.new(algorithm)
    h.update(value.encode("utf-8"))
    return h.hexdigest()


def parse_iso_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse an ISO format date string to datetime.
    
    Args:
        date_str: ISO format date string (e.g., "2024-01-15T10:00:00Z").
    
    Returns:
        Parsed datetime or None if parsing fails.
    """
    if not date_str:
        return None
    
    try:
        # Handle 'Z' suffix
        if date_str.endswith("Z"):
            date_str = date_str[:-1] + "+00:00"
        return datetime.fromisoformat(date_str)
    except (ValueError, AttributeError):
        return None


def days_since(date_value: Optional[datetime]) -> float:
    """
    Calculate days elapsed since a given date.
    
    Args:
        date_value: The date to compare from.
    
    Returns:
        Days elapsed (float). Returns 365.0 if date_value is None.
    """
    if not date_value:
        return 365.0
    
    try:
        now = datetime.now(timezone.utc)
        if date_value.tzinfo is None:
            date_value = date_value.replace(tzinfo=timezone.utc)
        return (now - date_value).total_seconds() / 86400
    except (ValueError, AttributeError, TypeError):
        return 365.0


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length.
    
    Args:
        text: String to truncate.
        max_length: Maximum length including suffix.
        suffix: Suffix to append when truncated.
    
    Returns:
        Truncated string.
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def extract_repo_from_url(url: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extract owner and repo name from a GitHub URL.
    
    Args:
        url: GitHub repository or issue URL.
    
    Returns:
        Tuple of (owner, repo) or (None, None) if not parseable.
    """
    patterns = [
        r"github\.com/([^/]+)/([^/]+)",
        r"api\.github\.com/repos/([^/]+)/([^/]+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            owner = match.group(1)
            repo = match.group(2).split("/")[0].split("?")[0].split("#")[0]
            return owner, repo
    
    return None, None


def chunk_list(items: List[T], chunk_size: int) -> List[List[T]]:
    """
    Split a list into chunks of specified size.
    
    Args:
        items: List to chunk.
        chunk_size: Maximum size of each chunk.
    
    Returns:
        List of chunks.
    """
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def safe_get(obj: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Safely get a nested value from a dictionary.
    
    Args:
        obj: Dictionary to traverse.
        *keys: Keys to follow.
        default: Default value if key not found.
    
    Returns:
        Value at the nested key path or default.
    """
    current = obj
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
        if current is None:
            return default
    return current


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge multiple dictionaries (later ones override).
    
    Args:
        *dicts: Dictionaries to merge.
    
    Returns:
        Merged dictionary.
    """
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result
