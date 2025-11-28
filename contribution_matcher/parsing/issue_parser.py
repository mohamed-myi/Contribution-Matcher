import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from contribution_matcher.parsing.skill_extractor import analyze_job_text
from contribution_matcher.config import SKILL_CATEGORIES


def _clean_text(text: str) -> str:
    """Remove excessive whitespace and normalize."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def find_difficulty(issue: str, labels: List[str]) -> Optional[str]:
    """

    Find difficulty level from issue body and labels.

    Returns - 'beginner', 'intermediate', 'advanced', or None

    """
    if not issue and not labels:
        return None

    text_lower = (issue or "").lower()
    labels_lower = [label.lower() for label in labels]

    # Define difficulty keywords
    beginner_labels = ["good first issue", "good-first-issue", "beginner", "beginner-friendly", 
                      "first-timers-only", "first timer", "easy", "starter"]

    intermediate_labels = ["intermediate", "medium", "moderate"]

    advanced_labels = ["advanced", "hard", "difficult", "expert", "complex"]
    
    for label in labels_lower:
        if any(b in label for b in beginner_labels):
            return "beginner"
        if any(i in label for i in intermediate_labels):
            return "intermediate"
        if any(a in label for a in advanced_labels):
            return "advanced"
    
    # Check issue body text
    beginner_patterns = [
        r'\b(beginner|beginner-friendly|good first issue|first timer|starter|easy)\b',
        r'\bshould take\s+(?:about\s+)?(\d+)\s*(?:hour|hr)',
        r'\btakes?\s+(?:about\s+)?(\d+)\s*(?:hour|hr)',
    ]
    
    advanced_patterns = [
        r'\b(advanced|expert|complex|difficult|hard|challenging)\b',
        r'\b(requires|needs)\s+(?:deep|extensive|significant)\s+(?:knowledge|experience|understanding)',
    ]
    
    for pattern in beginner_patterns:
        match = re.search(pattern, text_lower)
        if match:
            # If it mentions hours and it's <= 3 hours, likely beginner
            if match.groups():
                try:
                    hours = int(match.group(1))
                    if hours <= 3:
                        return "beginner"
                except (ValueError, IndexError):
                    pass
            return "beginner"
    
    for pattern in advanced_patterns:
        if re.search(pattern, text_lower):
            return "advanced"
    
    # Default to intermediate if unclear
    return "intermediate"


def find_technologies(
    issue: str,
    repo_languages: Optional[Dict[str, int]] = None,
    repo_topics: Optional[List[str]] = None
) -> List[Tuple[str, Optional[str]]]:
    """

    Find technologies from issue body, repo languages, and topics.

    Returns - List of (technology, category) tuples

    """
    technologies = []

    # Extract from issue body using skill_extractor
    if issue:
        _, skills, _ = analyze_job_text(issue)
        technologies.extend(skills)
    
    # Extract from repo languages
    if repo_languages:
        for lang in repo_languages.keys():
            # Normalize language name
            lang_lower = lang.lower()
            # Check if it matches any skill category
            for category, skills in SKILL_CATEGORIES.items():
                if lang_lower in [s.lower() for s in skills]:
                    if (lang, category) not in technologies:
                        technologies.append((lang, category))
                    break
            else:
                # Add as uncategorized
                if (lang, None) not in technologies:
                    technologies.append((lang, None))
    
    # Extract from repo topics
    if repo_topics:
        for topic in repo_topics:
            topic_lower = topic.lower()
            # Check if topic matches any skill
            for category, skills in SKILL_CATEGORIES.items():
                if topic_lower in [s.lower() for s in skills]:
                    if (topic, category) not in technologies:
                        technologies.append((topic, category))
                    break
    
    return technologies


def categorize_technologies(technologies: List[Tuple[str, Optional[str]]]) -> Dict[str, List[str]]:
    """
    Group technologies by category.
    
    Returns:
        Dictionary mapping category to list of technologies
    """
    categorized = {}
    for tech, category in technologies:
        if category:
            if category not in categorized:
                categorized[category] = []
            if tech not in categorized[category]:
                categorized[category].append(tech)
        else:
            # Uncategorized
            if "uncategorized" not in categorized:
                categorized["uncategorized"] = []
            if tech not in categorized["uncategorized"]:
                categorized["uncategorized"].append(tech)
    return categorized


def find_time_estimate(issue: str) -> Optional[str]:
    """

    Find time estimate from issue body.

    Returns - Time estimate string (e.g., "2-3 hours", "1 day", "weekend project") or None

    """
    if not issue:
        return None

    text_lower = issue.lower()
    
    # Patterns for time estimates
    patterns = [
        (r'should take\s+(?:about\s+)?(\d+)\s*(?:-\s*(\d+))?\s*(?:hour|hr|hours|hrs)', 'hours'),
        (r'takes?\s+(?:about\s+)?(\d+)\s*(?:-\s*(\d+))?\s*(?:hour|hr|hours|hrs)', 'hours'),
        (r'(\d+)\s*(?:-\s*(\d+))?\s*(?:hour|hr|hours|hrs)', 'hours'),
        (r'(\d+)\s*(?:-\s*(\d+))?\s*(?:day|days)', 'days'),
        (r'weekend\s+project', 'weekend'),
        (r'small\s+task', 'small'),
        (r'quick\s+(?:fix|task|change)', 'quick'),
    ]
    
    for pattern, unit in patterns:
        match = re.search(pattern, text_lower)
        if match:
            if unit == 'hours':
                if match.group(2):
                    return f"{match.group(1)}-{match.group(2)} hours"
                else:
                    return f"{match.group(1)} hour{'s' if int(match.group(1)) != 1 else ''}"
            elif unit == 'days':
                if match.group(2):
                    return f"{match.group(1)}-{match.group(2)} days"
                else:
                    return f"{match.group(1)} day{'s' if int(match.group(1)) != 1 else ''}"
            elif unit == 'weekend':
                return "weekend project"
            elif unit == 'small':
                return "small task"
            elif unit == 'quick':
                return "quick task"
    
    return None


def classify_issue_type(issue: str, labels: List[str]) -> Optional[str]:
    """

    Classify issue type.

    Returns - 'bug', 'feature', 'documentation', 'testing', 'refactoring', or None

    """
    if not issue and not labels:
        return None

    text_lower = (issue or "").lower()
    labels_lower = [label.lower() for label in labels]
    
    # Check labels first
    type_labels = {
        'bug': ['bug', 'bugfix', 'bug-fix', 'defect', 'error'],
        'feature': ['feature', 'enhancement', 'improvement', 'new'],
        'documentation': ['documentation', 'docs', 'doc', 'readme'],
        'testing': ['test', 'testing', 'tests', 'coverage'],
        'refactoring': ['refactor', 'refactoring', 'cleanup', 'clean-up'],
    }
    
    for issue_type, keywords in type_labels.items():
        for label in labels_lower:
            if any(kw in label for kw in keywords):
                return issue_type
    
    # Check issue body text
    bug_patterns = [
        r'\b(bug|error|issue|problem|broken|fails?|doesn\'?t work|not working)\b',
        r'\b(fix|fixes?|fixed)\b',
    ]
    
    feature_patterns = [
        r'\b(feature|add|implement|new functionality|enhancement|improve)\b',
        r'\b(should|could|would like to|proposal)\b',
    ]
    
    doc_patterns = [
        r'\b(documentation|docs?|readme|guide|tutorial|example)\b',
    ]
    
    test_patterns = [
        r'\b(test|testing|tests?|coverage|spec|specification)\b',
    ]
    
    refactor_patterns = [
        r'\b(refactor|refactoring|cleanup|clean up|restructure|optimize)\b',
    ]
    
    if any(re.search(p, text_lower) for p in bug_patterns):
        return "bug"
    if any(re.search(p, text_lower) for p in feature_patterns):
        return "feature"
    if any(re.search(p, text_lower) for p in doc_patterns):
        return "documentation"
    if any(re.search(p, text_lower) for p in test_patterns):
        return "testing"
    if any(re.search(p, text_lower) for p in refactor_patterns):
        return "refactoring"
    
    return None


def parse_issue(issue_data: Dict, repo_metadata: Optional[Dict] = None) -> Dict:
    """

    Parse a GitHub issue and extract structured information.

    Returns - Dictionary with parsed issue data

    """
    issue_body = issue_data.get("body", "") or ""
    labels = [label.get("name", "") for label in issue_data.get("labels", [])]

    # Extract repo info from issue URL
    repo_url = issue_data.get("repository_url", "")
    repo_owner = None
    repo_name = None
    if repo_url:
        parts = repo_url.replace("https://api.github.com/repos/", "").split("/")
        if len(parts) >= 2:
            repo_owner, repo_name = parts[0], parts[1]

    # Get repo metadata if not provided
    if repo_metadata is None and repo_owner and repo_name:
        from contribution_matcher.database import get_repo_metadata
        repo_metadata = get_repo_metadata(repo_owner, repo_name)

    repo_languages = repo_metadata.get("languages", {}) if repo_metadata else {}
    repo_topics = repo_metadata.get("topics", []) if repo_metadata else []

    # Extract all fields
    difficulty = find_difficulty(issue_body, labels)
    technologies = find_technologies(issue_body, repo_languages, repo_topics)
    time_estimate = find_time_estimate(issue_body)
    issue_type = classify_issue_type(issue_body, labels)
    
    # Get repo stats
    repo_stars = repo_metadata.get("stars") if repo_metadata else None
    repo_forks = repo_metadata.get("forks") if repo_metadata else None
    last_commit_date = repo_metadata.get("last_commit_date") if repo_metadata else None
    contributor_count = repo_metadata.get("contributor_count") if repo_metadata else None
    
    # Check if repo is active (recent commits within last 6 months)
    is_active = 1
    if last_commit_date:
        try:
            commit_date = datetime.fromisoformat(last_commit_date.replace('Z', '+00:00'))
            six_months_ago = datetime.now(commit_date.tzinfo) - timedelta(days=180)
            if commit_date < six_months_ago:
                is_active = 0
        except (ValueError, AttributeError):
            pass
    
    # Build full repo URL
    full_repo_url = None
    if repo_owner and repo_name:
        full_repo_url = f"https://github.com/{repo_owner}/{repo_name}"
    
    return {
        "title": issue_data.get("title", ""),
        "url": issue_data.get("html_url", ""),
        "body": issue_body,
        "repo_owner": repo_owner,
        "repo_name": repo_name,
        "repo_url": full_repo_url,
        "difficulty": difficulty,
        "issue_type": issue_type,
        "time_estimate": time_estimate,
        "labels": labels,
        "technologies": technologies,
        "repo_stars": repo_stars,
        "repo_forks": repo_forks,
        "repo_languages": repo_languages,
        "repo_topics": repo_topics,
        "last_commit_date": last_commit_date,
        "contributor_count": contributor_count,
        "is_active": is_active,
        "updated_at": issue_data.get("updated_at"),
    }

