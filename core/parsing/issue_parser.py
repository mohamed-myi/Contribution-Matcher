"""Issue parsing module for extracting structured information from GitHub issues."""

import re
from datetime import datetime, timedelta

from core.constants import SKILL_CATEGORIES
from core.parsing.skill_extractor import analyze_job_text

# Pre-compiled regex patterns for performance
_WHITESPACE_PATTERN = re.compile(r"\s+")

# Difficulty patterns
_BEGINNER_PATTERNS = [
    re.compile(
        r"\b(beginner|beginner-friendly|good first issue|first timer|starter|easy)\b", re.IGNORECASE
    ),
    re.compile(r"\bshould take\s+(?:about\s+)?(\d+)\s*(?:hour|hr)", re.IGNORECASE),
    re.compile(r"\btakes?\s+(?:about\s+)?(\d+)\s*(?:hour|hr)", re.IGNORECASE),
]
_ADVANCED_PATTERNS = [
    re.compile(r"\b(advanced|expert|complex|difficult|hard|challenging)\b", re.IGNORECASE),
    re.compile(
        r"\b(requires|needs)\s+(?:deep|extensive|significant)\s+(?:knowledge|experience|understanding)",
        re.IGNORECASE,
    ),
]

# Time estimate patterns
_TIME_PATTERNS = [
    (
        re.compile(
            r"should take\s+(?:about\s+)?(\d+)\s*(?:-\s*(\d+))?\s*(?:hour|hr|hours|hrs)",
            re.IGNORECASE,
        ),
        "hours",
    ),
    (
        re.compile(
            r"takes?\s+(?:about\s+)?(\d+)\s*(?:-\s*(\d+))?\s*(?:hour|hr|hours|hrs)", re.IGNORECASE
        ),
        "hours",
    ),
    (re.compile(r"(\d+)\s*(?:-\s*(\d+))?\s*(?:hour|hr|hours|hrs)", re.IGNORECASE), "hours"),
    (re.compile(r"(\d+)\s*(?:-\s*(\d+))?\s*(?:day|days)", re.IGNORECASE), "days"),
    (re.compile(r"weekend\s+project", re.IGNORECASE), "weekend"),
    (re.compile(r"small\s+task", re.IGNORECASE), "small"),
    (re.compile(r"quick\s+(?:fix|task|change)", re.IGNORECASE), "quick"),
]

# Issue type patterns
_BUG_PATTERNS = [
    re.compile(
        r"\b(bug|error|issue|problem|broken|fails?|doesn\'?t work|not working)\b", re.IGNORECASE
    ),
    re.compile(r"\b(fix|fixes?|fixed)\b", re.IGNORECASE),
]
_FEATURE_PATTERNS = [
    re.compile(r"\b(feature|add|implement|new functionality|enhancement|improve)\b", re.IGNORECASE),
    re.compile(r"\b(should|could|would like to|proposal)\b", re.IGNORECASE),
]
_DOC_PATTERNS = [
    re.compile(r"\b(documentation|docs?|readme|guide|tutorial|example)\b", re.IGNORECASE)
]
_TEST_PATTERNS = [
    re.compile(r"\b(test|testing|tests?|coverage|spec|specification)\b", re.IGNORECASE)
]
_REFACTOR_PATTERNS = [
    re.compile(r"\b(refactor|refactoring|cleanup|clean up|restructure|optimize)\b", re.IGNORECASE)
]

# Label keywords for issue types
_TYPE_LABELS = {
    "bug": frozenset(["bug", "bugfix", "bug-fix", "defect", "error"]),
    "feature": frozenset(["feature", "enhancement", "improvement", "new"]),
    "documentation": frozenset(["documentation", "docs", "doc", "readme"]),
    "testing": frozenset(["test", "testing", "tests", "coverage"]),
    "refactoring": frozenset(["refactor", "refactoring", "cleanup", "clean-up"]),
}

# Difficulty label keywords
_BEGINNER_LABELS = frozenset(
    [
        "good first issue",
        "good-first-issue",
        "beginner",
        "beginner-friendly",
        "first-timers-only",
        "first timer",
        "easy",
        "starter",
    ]
)
_INTERMEDIATE_LABELS = frozenset(["intermediate", "medium", "moderate"])
_ADVANCED_LABELS = frozenset(["advanced", "hard", "difficult", "expert", "complex"])


def _clean_text(text: str) -> str:
    """Remove excessive whitespace and normalize."""
    if not text:
        return ""
    return _WHITESPACE_PATTERN.sub(" ", text).strip()


def find_difficulty(issue: str, labels: list[str]) -> str | None:
    """
    Find difficulty level from issue body and labels.

    Returns: 'beginner', 'intermediate', 'advanced', or None
    """
    if not issue and not labels:
        return None

    labels_lower = [label.lower() for label in labels]

    # Check labels first (fastest)
    for label in labels_lower:
        if any(b in label for b in _BEGINNER_LABELS):
            return "beginner"
        if any(i in label for i in _INTERMEDIATE_LABELS):
            return "intermediate"
        if any(a in label for a in _ADVANCED_LABELS):
            return "advanced"

    # Check issue body patterns
    text_lower = (issue or "").lower()

    for pattern in _BEGINNER_PATTERNS:
        match = pattern.search(text_lower)
        if match:
            if match.groups():
                try:
                    hours = int(match.group(1))
                    if hours <= 3:
                        return "beginner"
                except (ValueError, IndexError):
                    pass
            return "beginner"

    for pattern in _ADVANCED_PATTERNS:
        if pattern.search(text_lower):
            return "advanced"

    return "intermediate"


def find_technologies(
    issue: str, repo_languages: dict[str, int] | None = None, repo_topics: list[str] | None = None
) -> list[tuple[str, str | None]]:
    """
    Find technologies from issue body, repo languages, and topics.

    Returns: List of (technology, category) tuples
    """
    technologies: list[tuple[str, str | None]] = []
    seen: set = set()

    # Extract from issue body
    if issue:
        _, skills, _ = analyze_job_text(issue)
        for tech, category in skills:
            key = (tech.lower(), category)
            if key not in seen:
                seen.add(key)
                technologies.append((tech, category))

    # Extract from repo languages
    if repo_languages:
        for lang in repo_languages:
            lang_lower = lang.lower()
            category = None
            for cat, skills in SKILL_CATEGORIES.items():
                if lang_lower in [s.lower() for s in skills]:  # type: ignore[attr-defined]
                    category = cat
                    break

            key = (lang_lower, category)
            if key not in seen:
                seen.add(key)
                technologies.append((lang, category))

    # Extract from repo topics
    if repo_topics:
        for topic in repo_topics:
            topic_lower = topic.lower()
            for cat, skills in SKILL_CATEGORIES.items():
                if topic_lower in [s.lower() for s in skills]:  # type: ignore[attr-defined]
                    key = (topic_lower, cat)
                    if key not in seen:
                        seen.add(key)
                        technologies.append((topic, cat))
                    break

    return technologies


def categorize_technologies(technologies: list[tuple[str, str | None]]) -> dict[str, list[str]]:
    """Group technologies by category."""
    categorized: dict[str, list[str]] = {}

    for tech, category in technologies:
        cat_key = category or "uncategorized"
        if cat_key not in categorized:
            categorized[cat_key] = []
        if tech not in categorized[cat_key]:
            categorized[cat_key].append(tech)

    return categorized


def find_time_estimate(issue: str) -> str | None:
    """
    Find time estimate from issue body.

    Returns: Time estimate string or None
    """
    if not issue:
        return None

    text_lower = issue.lower()

    for pattern, unit in _TIME_PATTERNS:
        match = pattern.search(text_lower)
        if match:
            if unit == "hours":
                n1 = match.group(1)
                n2 = match.group(2) if len(match.groups()) > 1 else None
                if n2:
                    return f"{n1}-{n2} hours"
                return f"{n1} hour{'s' if int(n1) != 1 else ''}"
            elif unit == "days":
                n1 = match.group(1)
                n2 = match.group(2) if len(match.groups()) > 1 else None
                if n2:
                    return f"{n1}-{n2} days"
                return f"{n1} day{'s' if int(n1) != 1 else ''}"
            elif unit == "weekend":
                return "weekend project"
            elif unit == "small":
                return "small task"
            elif unit == "quick":
                return "quick task"

    return None


def classify_issue_type(issue: str, labels: list[str]) -> str | None:
    """
    Classify issue type.

    Returns: 'bug', 'feature', 'documentation', 'testing', 'refactoring', or None
    """
    if not issue and not labels:
        return None

    labels_lower = [label.lower() for label in labels]

    # Check labels first (fastest)
    for issue_type, keywords in _TYPE_LABELS.items():
        for label in labels_lower:
            if any(kw in label for kw in keywords):
                return issue_type

    # Check issue body patterns
    text_lower = (issue or "").lower()

    if any(p.search(text_lower) for p in _BUG_PATTERNS):
        return "bug"
    if any(p.search(text_lower) for p in _FEATURE_PATTERNS):
        return "feature"
    if any(p.search(text_lower) for p in _DOC_PATTERNS):
        return "documentation"
    if any(p.search(text_lower) for p in _TEST_PATTERNS):
        return "testing"
    if any(p.search(text_lower) for p in _REFACTOR_PATTERNS):
        return "refactoring"

    return None


def parse_issue(issue_data: dict, repo_metadata: dict | None = None) -> dict:
    """
    Parse a GitHub issue and extract structured information.

    Returns: Dictionary with parsed issue data
    """
    issue_body = issue_data.get("body", "") or ""
    labels = [label.get("name", "") for label in issue_data.get("labels", [])]

    # Extract repo info from issue URL
    repo_url = issue_data.get("repository_url", "")
    repo_owner, repo_name = None, None
    if repo_url:
        parts = repo_url.replace("https://api.github.com/repos/", "").split("/")
        if len(parts) >= 2:
            repo_owner, repo_name = parts[0], parts[1]

    # Get repo metadata if not provided
    if repo_metadata is None and repo_owner and repo_name:
        from core.db import db
        from core.repositories import RepoMetadataRepository

        if db.is_initialized:
            with db.session() as session:
                repo_repo = RepoMetadataRepository(session)
                cached = repo_repo.get(repo_owner, repo_name)
                if cached:
                    repo_metadata = cached.to_dict()

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
            commit_date = datetime.fromisoformat(last_commit_date.replace("Z", "+00:00"))
            six_months_ago = datetime.now(commit_date.tzinfo) - timedelta(days=180)
            if commit_date < six_months_ago:
                is_active = 0
        except (ValueError, AttributeError):
            pass

    # Build full repo URL
    full_repo_url = (
        f"https://github.com/{repo_owner}/{repo_name}" if repo_owner and repo_name else None
    )

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
