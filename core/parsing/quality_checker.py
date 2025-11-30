# Quality checker module for validating issue quality

import re
from typing import Dict, List, Optional, Tuple


def check_issue_quality(issue: Dict, repo_metadata: Optional[Dict] = None) -> Tuple[bool, List[str]]:
    '''
    Check issue quality and return validation result with reasons.
    
    Args:
        issue: Issue dictionary from GitHub API
        repo_metadata: Optional repository metadata
        
    Returns:
        Tuple of (is_valid, list_of_issues)
    '''
    issues = []
    
    # Check if issue is closed
    if issue.get("state", "").lower() != "open":
        issues.append("Issue is not open")
        return (False, issues)
    
    # Check for spam indicators
    spam_indicators = _detect_spam(issue)
    if spam_indicators:
        issues.extend(spam_indicators)
    
    # Check issue completeness
    completeness_issues = _check_completeness(issue)
    if completeness_issues:
        issues.extend(completeness_issues)
    
    # Check for duplicate patterns
    duplicate_indicators = _check_duplicate_patterns(issue)
    if duplicate_indicators:
        issues.extend(duplicate_indicators)
    
    is_valid = len(issues) == 0
    return (is_valid, issues)


def _detect_spam(issue: Dict) -> List[str]:
    '''
    Detect spam or low-quality issues.
    
    Returns - List of spam indicators found
    '''
    issues = []
    body = (issue.get("body") or "").lower()
    title = (issue.get("title") or "").lower()
    
    # Check for very short content
    if len(body) < 20 and len(title) < 10:
        issues.append("Very short content (possible spam)")
    
    # Check for spam keywords
    spam_keywords = [
        "buy", "sell", "cheap", "discount", "click here", "visit now",
        "make money", "get rich", "free money", "lottery", "winner",
        "congratulations", "urgent", "limited time", "act now"
    ]
    
    text = body + " " + title
    for keyword in spam_keywords:
        if keyword in text:
            issues.append(f"Contains spam keyword: {keyword}")
            break
    
    # Check for excessive links (more than 3)
    link_pattern = r'https?://[^\s]+'
    links = re.findall(link_pattern, text)
    if len(links) > 3:
        issues.append("Excessive links (possible spam)")
    
    # Check for excessive capitalization
    if len(title) > 0:
        caps_ratio = sum(1 for c in title if c.isupper()) / len(title)
        if caps_ratio > 0.5 and len(title) > 10:
            issues.append("Excessive capitalization (possible spam)")
    
    return issues


def _check_completeness(issue: Dict) -> List[str]:
    '''
    Check if issue has sufficient information.
    
    Returns - List of completeness issues
    '''
    issues = []
    body = issue.get("body") or ""
    title = issue.get("title") or ""
    
    # Check for empty or very short body
    if len(body.strip()) < 10:
        issues.append("Issue body is too short or empty")
    
    # Check for missing title
    if not title or len(title.strip()) < 5:
        issues.append("Issue title is too short or missing")
    
    # Check for placeholder text
    placeholder_patterns = [
        r'\btodo\b', r'\bfixme\b', r'\bxxx\b', r'\[.*?\]', r'\(.*?\)',
        r'placeholder', r'example', r'sample'
    ]
    
    body_lower = body.lower()
    for pattern in placeholder_patterns:
        if re.search(pattern, body_lower, re.IGNORECASE):
            # Only flag if it's a significant portion of the content
            matches = len(re.findall(pattern, body_lower, re.IGNORECASE))
            if matches > 2:
                issues.append("Contains placeholder text")
                break
    
    return issues


def _check_duplicate_patterns(issue: Dict) -> List[str]:
    '''
    Check for patterns that suggest duplicate issues.
    
    Returns - List of duplicate indicators
    '''
    issues = []
    body = (issue.get("body") or "").lower()
    title = (issue.get("title") or "").lower()
    
    # Check for duplicate keywords
    duplicate_keywords = ["duplicate", "same as", "already reported", "see issue"]
    text = body + " " + title
    for keyword in duplicate_keywords:
        if keyword in text:
            issues.append(f"Possible duplicate: contains '{keyword}'")
            break
    
    return issues


def validate_repo_quality(repo_metadata: Optional[Dict]) -> Tuple[bool, List[str]]:
    '''
    Validate repository quality.
    
    Returns - Tuple of (is_valid, list_of_issues)
    '''
    if not repo_metadata:
        return (False, ["Repository metadata not available"])
    
    issues = []
    
    # Check stars
    stars = repo_metadata.get("stars", 0) or 0
    if stars < 1:
        issues.append("Repository has no stars")
    
    # Check if repository is archived
    if repo_metadata.get("archived", False):
        issues.append("Repository is archived")
    
    # Check if repository is disabled
    if repo_metadata.get("disabled", False):
        issues.append("Repository is disabled")
    
    is_valid = len(issues) == 0
    return (is_valid, issues)


def filter_issues_by_quality(issues: List[Dict], repo_metadata_map: Optional[Dict] = None) -> List[Dict]:
    '''
    Filter issues by quality criteria.
    
    Args:
        issues: List of issue dictionaries
        repo_metadata_map: Optional dict mapping repo URLs to metadata
        
    Returns:
        Filtered list of valid issues
    '''
    filtered = []
    
    for issue in issues:
        repo_url = issue.get("repository_url", "")
        repo_meta = None
        
        if repo_metadata_map and repo_url in repo_metadata_map:
            repo_meta = repo_metadata_map[repo_url]
        
        # Check issue quality
        is_valid, quality_issues = check_issue_quality(issue, repo_meta)
        
        # Check repo quality if metadata available
        if repo_meta:
            repo_valid, repo_issues = validate_repo_quality(repo_meta)
            if not repo_valid:
                quality_issues.extend(repo_issues)
                is_valid = False
        
        if is_valid:
            filtered.append(issue)
    
    return filtered

