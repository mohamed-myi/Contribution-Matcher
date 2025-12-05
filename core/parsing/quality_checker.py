"""Quality checker module for validating issue quality."""

import re
from typing import Dict, List, Optional, Tuple

# Pre-compiled regex patterns for performance
_LINK_PATTERN = re.compile(r'https?://[^\s]+')
_PLACEHOLDER_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [r'\btodo\b', r'\bfixme\b', r'\bxxx\b', r'\[.*?\]', r'\(.*?\)', r'placeholder', r'example', r'sample']
]

# Constants
_SPAM_KEYWORDS = frozenset([
    "buy", "sell", "cheap", "discount", "click here", "visit now",
    "make money", "get rich", "free money", "lottery", "winner",
    "congratulations", "urgent", "limited time", "act now"
])

_DUPLICATE_KEYWORDS = frozenset(["duplicate", "same as", "already reported", "see issue"])


def check_issue_quality(issue: Dict, repo_metadata: Optional[Dict] = None) -> Tuple[bool, List[str]]:
    """
    Check issue quality and return validation result with reasons.
    
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues: List[str] = []
    
    if issue.get("state", "").lower() != "open":
        return (False, ["Issue is not open"])
    
    issues.extend(_detect_spam(issue))
    issues.extend(_check_completeness(issue))
    issues.extend(_check_duplicate_patterns(issue))
    
    return (len(issues) == 0, issues)


def _detect_spam(issue: Dict) -> List[str]:
    """Detect spam or low-quality issues."""
    issues: List[str] = []
    body = (issue.get("body") or "").lower()
    title = (issue.get("title") or "").lower()
    
    # Check for very short content
    if len(body) < 20 and len(title) < 10:
        issues.append("Very short content (possible spam)")
    
    # Check for spam keywords
    text = f"{body} {title}"
    for keyword in _SPAM_KEYWORDS:
        if keyword in text:
            issues.append(f"Contains spam keyword: {keyword}")
            break
    
    # Check for excessive links (> 3)
    if len(_LINK_PATTERN.findall(text)) > 3:
        issues.append("Excessive links (possible spam)")
    
    # Check for excessive capitalization
    if len(title) > 10:
        caps_ratio = sum(1 for c in title if c.isupper()) / len(title)
        if caps_ratio > 0.5:
            issues.append("Excessive capitalization (possible spam)")
    
    return issues


def _check_completeness(issue: Dict) -> List[str]:
    """Check if issue has sufficient information."""
    issues: List[str] = []
    body = issue.get("body") or ""
    title = issue.get("title") or ""
    
    if len(body.strip()) < 10:
        issues.append("Issue body is too short or empty")
    
    if len(title.strip()) < 5:
        issues.append("Issue title is too short or missing")
    
    # Check for placeholder text
    body_lower = body.lower()
    placeholder_count = sum(len(p.findall(body_lower)) for p in _PLACEHOLDER_PATTERNS)
    if placeholder_count > 2:
        issues.append("Contains placeholder text")
    
    return issues


def _check_duplicate_patterns(issue: Dict) -> List[str]:
    """Check for patterns that suggest duplicate issues."""
    body = (issue.get("body") or "").lower()
    title = (issue.get("title") or "").lower()
    text = f"{body} {title}"
    
    for keyword in _DUPLICATE_KEYWORDS:
        if keyword in text:
            return [f"Possible duplicate: contains '{keyword}'"]
    return []


def validate_repo_quality(repo_metadata: Optional[Dict]) -> Tuple[bool, List[str]]:
    """Validate repository quality."""
    if not repo_metadata:
        return (False, ["Repository metadata not available"])
    
    issues: List[str] = []
    
    if (repo_metadata.get("stars", 0) or 0) < 1:
        issues.append("Repository has no stars")
    if repo_metadata.get("archived", False):
        issues.append("Repository is archived")
    if repo_metadata.get("disabled", False):
        issues.append("Repository is disabled")
    
    return (len(issues) == 0, issues)


def filter_issues_by_quality(issues: List[Dict], repo_metadata_map: Optional[Dict] = None) -> List[Dict]:
    """Filter issues by quality criteria."""
    filtered = []
    
    for issue in issues:
        repo_url = issue.get("repository_url", "")
        repo_meta = repo_metadata_map.get(repo_url) if repo_metadata_map else None
        
        is_valid, _ = check_issue_quality(issue, repo_meta)
        
        if repo_meta:
            repo_valid, _ = validate_repo_quality(repo_meta)
            is_valid = is_valid and repo_valid
        
        if is_valid:
            filtered.append(issue)
    
    return filtered
