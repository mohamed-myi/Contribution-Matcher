import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

from contribution_matcher.config import GITHUB_API_BASE, GOOD_FIRST_ISSUE_LABELS, HELP_WANTED_LABELS
from contribution_matcher.database import get_repo_metadata, upsert_repo_metadata

load_dotenv()

GITHUB_TOKEN = os.getenv("PAT_TOKEN")
RATE_LIMIT_REMAINING = 5000
RATE_LIMIT_RESET = 0


def _get_headers() -> Dict[str, str]:
    """Get headers for GitHub API requests."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ContributionMatcher/1.0"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


def _handle_rate_limit(response: requests.Response) -> None:
    """Handle rate limiting by checking headers and waiting if needed."""
    global RATE_LIMIT_REMAINING, RATE_LIMIT_RESET
    
    if "X-RateLimit-Remaining" in response.headers:
        RATE_LIMIT_REMAINING = int(response.headers["X-RateLimit-Remaining"])
        RATE_LIMIT_RESET = int(response.headers.get("X-RateLimit-Reset", 0))
    
    if RATE_LIMIT_REMAINING < 10:
        # Wait until rate limit resets
        if RATE_LIMIT_RESET > 0:
            wait_time = RATE_LIMIT_RESET - int(time.time()) + 1
            if wait_time > 0:
                print(f"Rate limit approaching. Waiting {wait_time} seconds...")
                time.sleep(wait_time)


def _make_request(url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
    """Make a GitHub API request with rate limiting and error handling."""
    global RATE_LIMIT_REMAINING
    
    if RATE_LIMIT_REMAINING < 10:
        _handle_rate_limit(requests.Response())
    
    try:
        response = requests.get(url, headers=_get_headers(), params=params, timeout=30)
        _handle_rate_limit(response)
        
        if response.status_code == 200:
            return response
        elif response.status_code == 404:
            return None
        elif response.status_code == 403:
            # Rate limited
            if "X-RateLimit-Reset" in response.headers:
                reset_time = int(response.headers["X-RateLimit-Reset"])
                wait_time = reset_time - int(time.time()) + 1
                if wait_time > 0:
                    print(f"Rate limited. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    return _make_request(url, params)  # Retry
            return None
        else:
            print(f"GitHub API error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"Error making GitHub API request: {e}")
        return None


def search_issues(
    labels: Optional[List[str]] = None,
    language: Optional[str] = None,
    min_stars: Optional[int] = None,
    limit: int = 100
) -> List[Dict]:
    """
    Search GitHub for issues with specified criteria.
    
    Args:
        labels: List of labels to search for (e.g., ["good first issue"])
        language: Programming language filter
        min_stars: Minimum repository stars
        limit: Maximum number of issues to return
        
    Returns:
        List of issue dictionaries
    """
    if labels is None:
        labels = GOOD_FIRST_ISSUE_LABELS + HELP_WANTED_LABELS
    
    all_issues = []
    page = 1
    per_page = min(100, limit)  # GitHub API max is 100 per page
    
    while len(all_issues) < limit:
        # Build query string
        query_parts = []
        
        # Add label filters (use OR logic for multiple labels)
        if len(labels) > 1:
            label_query = " OR ".join([f"label:{label}" for label in labels])
            query_parts.append(f"({label_query})")
        elif len(labels) == 1:
            query_parts.append(f"label:{labels[0]}")
        
        # Add language filter
        if language:
            query_parts.append(f"language:{language}")
        
        # Add state filter (only open issues)
        query_parts.append("state:open")
        
        query = " ".join(query_parts)
        
        params = {
            "q": query,
            "sort": "updated",
            "order": "desc",
            "per_page": per_page,
            "page": page
        }
        
        url = f"{GITHUB_API_BASE}/search/issues"
        response = _make_request(url, params)
        
        if not response:
            break
        
        data = response.json()
        items = data.get("items", [])
        
        if not items:
            break
        
        # Filter by min_stars if specified
        for item in items:
            repo_url = item.get("repository_url", "")
            if min_stars and repo_url:
                # Extract repo owner/name from URL
                parts = repo_url.replace(f"{GITHUB_API_BASE}/repos/", "").split("/")
                if len(parts) >= 2:
                    repo_owner, repo_name = parts[0], parts[1]
                    repo_meta = get_repo_metadata(repo_owner, repo_name)
                    if repo_meta and repo_meta.get("stars", 0) < min_stars:
                        continue
            
            all_issues.append(item)
            if len(all_issues) >= limit:
                break
        
        if len(items) < per_page:
            break
        
        page += 1
        time.sleep(0.5)  # Be nice to the API
    
    return all_issues[:limit]


def get_repo_metadata_from_api(repo_owner: str, repo_name: str, use_cache: bool = True) -> Optional[Dict]:
    """
    Fetch repository metadata from GitHub API or cache.
    
    Args:
        repo_owner: Repository owner username
        repo_name: Repository name
        use_cache: Whether to use cached data if available
        
    Returns:
        Dictionary with repo metadata or None
    """
    # Check cache first
    if use_cache:
        cached = get_repo_metadata(repo_owner, repo_name)
        if cached:
            # Check if cache is fresh (less than 24 hours old)
            cached_at = datetime.fromisoformat(cached.get("cached_at", "2000-01-01"))
            if datetime.now() - cached_at < timedelta(hours=24):
                return cached
    
    # Fetch from API
    url = f"{GITHUB_API_BASE}/repos/{repo_owner}/{repo_name}"
    response = _make_request(url)
    
    if not response:
        return None
    
    repo_data = response.json()
    
    # Extract languages
    languages_url = repo_data.get("languages_url", "")
    languages = {}
    if languages_url:
        lang_response = _make_request(languages_url)
        if lang_response:
            languages = lang_response.json()
    
    # Extract topics
    topics_url = f"{GITHUB_API_BASE}/repos/{repo_owner}/{repo_name}/topics"
    topics = []
    topics_response = _make_request(topics_url, params={"Accept": "application/vnd.github.mercy-preview+json"})
    if topics_response:
        topics_data = topics_response.json()
        topics = topics_data.get("names", [])
    
    # Get last commit date
    commits_url = f"{GITHUB_API_BASE}/repos/{repo_owner}/{repo_name}/commits"
    commits_response = _make_request(commits_url, params={"per_page": 1})
    last_commit_date = None
    if commits_response:
        commits = commits_response.json()
        if commits and len(commits) > 0:
            commit = commits[0]
            last_commit_date = commit.get("commit", {}).get("author", {}).get("date")
    
    # Get contributor count
    contributors_url = f"{GITHUB_API_BASE}/repos/{repo_owner}/{repo_name}/contributors"
    contributors_response = _make_request(contributors_url, params={"per_page": 1, "anon": "true"})
    contributor_count = None
    if contributors_response:
        # Use Link header to get total count if available
        link_header = contributors_response.headers.get("Link", "")
        if link_header:
            # Parse Link header to find last page
            # Format: <url>; rel="last"
            for link in link_header.split(","):
                if 'rel="last"' in link:
                    # Extract page number from URL
                    import re
                    match = re.search(r'page=(\d+)', link)
                    if match:
                        contributor_count = int(match.group(1)) * 100  # Approximate
        else:
            # Fallback: count contributors (limited to first page)
            contributors = contributors_response.json()
            contributor_count = len(contributors) if isinstance(contributors, list) else None
    
    metadata = {
        "repo_owner": repo_owner,
        "repo_name": repo_name,
        "stars": repo_data.get("stargazers_count"),
        "forks": repo_data.get("forks_count"),
        "languages": languages,
        "topics": topics,
        "last_commit_date": last_commit_date,
        "contributor_count": contributor_count,
    }
    
    # Cache the metadata
    upsert_repo_metadata(
        repo_owner=repo_owner,
        repo_name=repo_name,
        stars=metadata["stars"],
        forks=metadata["forks"],
        languages=metadata["languages"],
        topics=metadata["topics"],
        last_commit_date=metadata["last_commit_date"],
        contributor_count=metadata["contributor_count"],
    )
    
    return metadata


