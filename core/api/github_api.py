"""GitHub API client with rate limiting and caching."""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

from core.config import (
    GITHUB_API_BASE, 
    GITHUB_GRAPHQL_ENDPOINT, 
    GOOD_FIRST_ISSUE_LABELS, 
    HELP_WANTED_LABELS,
    DISCOVERY_LABELS,
    DISCOVERY_LANGUAGES,
)
from core.database import get_repo_metadata, upsert_repo_metadata
from core.logging import get_logger

load_dotenv()

logger = get_logger("github")

GITHUB_TOKEN = os.getenv("PAT_TOKEN")
RATE_LIMIT_REMAINING = 5000
RATE_LIMIT_RESET = 0

FAST_DISCOVERY = os.getenv("FAST_DISCOVERY", "true").lower() == "true"
CACHE_VALIDITY_DAYS = int(os.getenv("CACHE_VALIDITY_DAYS", "7"))


def _get_headers() -> Dict[str, str]:
    """Get headers for GitHub API requests."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ContributionMatcher/1.0"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


def _get_graphql_headers() -> Dict[str, str]:
    """Get headers for GitHub GraphQL API requests."""
    headers = {
        "Accept": "application/json",
        "User-Agent": "ContributionMatcher/1.0"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"bearer {GITHUB_TOKEN}"
    return headers


def _graphql_batch_fetch_repos(repo_list: List[tuple]) -> Dict[tuple, Optional[Dict]]:
    """Fetch metadata for multiple repositories using a single GraphQL query."""
    if not GITHUB_TOKEN:
        logger.warning("graphql_auth_required", message="GraphQL requires authentication")
        return {}
    
    if not repo_list:
        return {}
    
    results = {}
    chunk_size = 50
    
    for chunk_start in range(0, len(repo_list), chunk_size):
        chunk = repo_list[chunk_start:chunk_start + chunk_size]
        
        query_parts = []
        for i, (owner, name) in enumerate(chunk):
            alias = f"repo_{i}"
            query_parts.append(f'''
                {alias}: repository(owner: "{owner}", name: "{name}") {{
                    owner {{ login }}
                    name
                    stargazerCount
                    forkCount
                    languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{
                        edges {{
                            size
                            node {{ name }}
                        }}
                    }}
                    repositoryTopics(first: 10) {{
                        nodes {{ topic {{ name }} }}
                    }}
                    defaultBranchRef {{
                        target {{
                            ... on Commit {{
                                committedDate
                            }}
                        }}
                    }}
                }}
            ''')
        
        query = "query { " + " ".join(query_parts) + " }"
        
        try:
            response = requests.post(
                GITHUB_GRAPHQL_ENDPOINT,
                headers=_get_graphql_headers(),
                json={"query": query},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if "errors" in data:
                    for error in data.get("errors", []):
                        if "NOT_FOUND" not in str(error.get("type", "")):
                            logger.warning("graphql_error", error=error.get('message', 'Unknown'))
                
                repo_data = data.get("data", {})
                
                for i, (owner, name) in enumerate(chunk):
                    alias = f"repo_{i}"
                    repo_info = repo_data.get(alias)
                    
                    if repo_info:
                        languages = {}
                        for edge in repo_info.get("languages", {}).get("edges", []):
                            lang_name = edge.get("node", {}).get("name", "")
                            lang_size = edge.get("size", 0)
                            if lang_name:
                                languages[lang_name] = lang_size
                        
                        topics = [
                            node.get("topic", {}).get("name", "")
                            for node in repo_info.get("repositoryTopics", {}).get("nodes", [])
                            if node.get("topic", {}).get("name")
                        ]
                        
                        last_commit_date = None
                        default_branch = repo_info.get("defaultBranchRef")
                        if default_branch:
                            target = default_branch.get("target", {})
                            last_commit_date = target.get("committedDate")
                        
                        metadata = {
                            "repo_owner": owner,
                            "repo_name": name,
                            "stars": repo_info.get("stargazerCount"),
                            "forks": repo_info.get("forkCount"),
                            "languages": languages,
                            "topics": topics,
                            "last_commit_date": last_commit_date,
                            "contributor_count": None,
                        }
                        
                        results[(owner, name)] = metadata
                        
                        upsert_repo_metadata(
                            repo_owner=owner,
                            repo_name=name,
                            stars=metadata["stars"],
                            forks=metadata["forks"],
                            languages=metadata["languages"],
                            topics=metadata["topics"],
                            last_commit_date=metadata["last_commit_date"],
                            contributor_count=metadata["contributor_count"],
                        )
                    else:
                        results[(owner, name)] = None
                        
            elif response.status_code == 403:
                logger.warning("graphql_rate_limited", status=response.status_code)
                reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                if reset_time > 0:
                    wait_time = min(reset_time - int(time.time()) + 1, 300)
                    if wait_time > 0:
                        logger.info("rate_limit_wait", wait_seconds=wait_time)
                        time.sleep(wait_time)
                break
            else:
                logger.error("graphql_request_failed", status=response.status_code)
                
        except Exception as e:
            logger.error("graphql_exception", error=str(e), error_type=type(e).__name__)
            
        if chunk_start + chunk_size < len(repo_list):
            time.sleep(0.2)
    
    return results


def _handle_rate_limit(response: requests.Response) -> None:
    """Handle rate limiting by checking headers and waiting if needed."""
    global RATE_LIMIT_REMAINING, RATE_LIMIT_RESET
    
    if "X-RateLimit-Remaining" in response.headers:
        RATE_LIMIT_REMAINING = int(response.headers["X-RateLimit-Remaining"])
        RATE_LIMIT_RESET = int(response.headers.get("X-RateLimit-Reset", 0))
    
    if RATE_LIMIT_REMAINING < 10:
        if RATE_LIMIT_RESET > 0:
            wait_time = RATE_LIMIT_RESET - int(time.time()) + 1
            wait_time = min(wait_time, 300)
            if wait_time > 0:
                logger.info("rate_limit_approaching", wait_seconds=wait_time, remaining=RATE_LIMIT_REMAINING)
                time.sleep(wait_time)


def _make_request(url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
    """Make a GitHub API request with rate limiting and error handling."""
    global RATE_LIMIT_REMAINING
    
    if not GITHUB_TOKEN:
        logger.warning("no_token", message="PAT_TOKEN not found, using unauthenticated requests")
    
    if RATE_LIMIT_REMAINING < 10:
        _handle_rate_limit(requests.Response())
    
    try:
        response = requests.get(url, headers=_get_headers(), params=params, timeout=30)
        _handle_rate_limit(response)
        
        if response.status_code == 200:
            return response
        elif response.status_code == 404:
            logger.debug("api_not_found", url=url)
            return None
        elif response.status_code == 401:
            logger.error("api_auth_failed", url=url)
            return None
        elif response.status_code == 403:
            if "X-RateLimit-Reset" in response.headers:
                reset_time = int(response.headers["X-RateLimit-Reset"])
                wait_time = min(reset_time - int(time.time()) + 1, 300)
                if wait_time > 0:
                    logger.info("rate_limited_retry", wait_seconds=wait_time)
                    time.sleep(wait_time)
                    return _make_request(url, params)
            logger.error("rate_limited_no_reset")
            return None
        else:
            logger.error("api_error", status=response.status_code, url=url)
            return None
    except Exception as e:
        logger.error("request_exception", error=str(e), url=url)
        return None


def search_issues(
    labels: Optional[List[str]] = None,
    language: Optional[str] = None,
    min_stars: Optional[int] = None,
    limit: int = 100,
    apply_quality_filters: bool = True,
    use_expanded_labels: bool = True,
) -> List[Dict]:
    """
    Search GitHub for issues with specified criteria.
    
    Args:
        labels: List of labels to search for
        language: Programming language filter
        min_stars: Minimum repository stars
        limit: Maximum number of issues to return
        apply_quality_filters: Apply default quality filters
        use_expanded_labels: Use expanded label set for variety
        
    Returns:
        List of issue dictionaries
    """
    if labels is None:
        if use_expanded_labels:
            labels = DISCOVERY_LABELS[:8]
        else:
            labels = ["good first issue", "help wanted"]
    
    if apply_quality_filters and min_stars is None:
        min_stars = 10
    
    logger.info(
        "search_started",
        labels=labels[:5],
        language=language,
        min_stars=min_stars,
        limit=limit,
    )
    
    all_issues = []
    seen_urls = set()
    
    for label in labels:
        if len(all_issues) >= limit:
            break
        
        page = 1
        per_page = min(100, limit - len(all_issues))
        
        while len(all_issues) < limit:
            query_parts = []
            
            if " " in label:
                query_parts.append(f'label:"{label}"')
            else:
                query_parts.append(f"label:{label}")
            
            if language:
                query_parts.append(f"language:{language}")
            
            query_parts.append("state:open")
            query = " ".join(query_parts)
            
            params = {
                "q": query,
                "sort": "updated",
                "order": "desc",
                "per_page": per_page,
                "page": page
            }
            
            if page == 1:
                logger.debug("searching_label", label=label, query=query[:80])
            
            url = f"{GITHUB_API_BASE}/search/issues"
            response = _make_request(url, params)
            
            if not response:
                logger.warning("search_no_response", label=label, page=page)
                break
            
            data = response.json()
            total_count = data.get("total_count", 0)
            items = data.get("items", [])
            
            if page == 1:
                logger.debug("label_results", label=label, total_count=total_count)
            
            if not items:
                break
            
            for item in items:
                issue_url = item.get("html_url", "")
                if issue_url in seen_urls:
                    continue
                
                repo_url = item.get("repository_url", "")
                if min_stars and repo_url:
                    parts = repo_url.replace(f"{GITHUB_API_BASE}/repos/", "").split("/")
                    if len(parts) >= 2:
                        repo_owner, repo_name = parts[0], parts[1]
                        repo_meta = get_repo_metadata(repo_owner, repo_name)
                        if repo_meta and repo_meta.get("stars", 0) < min_stars:
                            continue
                
                all_issues.append(item)
                seen_urls.add(issue_url)
                
                if len(all_issues) >= limit:
                    break
            
            if len(items) < per_page or len(all_issues) >= limit:
                break
            
            page += 1
            time.sleep(0.5)
    
    logger.info("search_complete", issues_found=len(all_issues))
    return all_issues[:limit]


def batch_get_repo_metadata(
    repo_list: List[tuple],
    use_cache: bool = True,
    batch_size: int = 50,
    use_graphql: bool = True
) -> Dict[tuple, Optional[Dict]]:
    """
    Batch fetch repository metadata for multiple repositories.
    Uses GraphQL by default for efficiency (1 call instead of 5 per repo).
    """
    results = {}
    cache_validity = timedelta(days=CACHE_VALIDITY_DAYS)
    
    if use_cache:
        for repo_owner, repo_name in repo_list:
            cached = get_repo_metadata(repo_owner, repo_name)
            if cached:
                cached_at = datetime.fromisoformat(cached.get("cached_at", "2000-01-01"))
                if datetime.now() - cached_at < cache_validity:
                    results[(repo_owner, repo_name)] = cached
    
    remaining = [(owner, name) for owner, name in repo_list 
                 if (owner, name) not in results]
    
    if not remaining:
        return results
    
    logger.info("batch_fetch_metadata", repo_count=len(remaining))
    
    if use_graphql and GITHUB_TOKEN:
        graphql_results = _graphql_batch_fetch_repos(remaining)
        results.update(graphql_results)
        
        remaining = [(owner, name) for owner, name in remaining 
                     if (owner, name) not in results or results[(owner, name)] is None]
    
    if remaining:
        logger.info("rest_fallback", repo_count=len(remaining))
        for repo_owner, repo_name in remaining:
            if RATE_LIMIT_REMAINING < 5:
                wait_time = min(RATE_LIMIT_RESET - int(time.time()) + 1, 300)
                if wait_time > 0:
                    logger.info("rate_limit_wait", wait_seconds=wait_time)
                    time.sleep(wait_time)
            
            metadata = get_repo_metadata_from_api(repo_owner, repo_name, use_cache=False)
            results[(repo_owner, repo_name)] = metadata
            time.sleep(0.1)
    
    return results


def check_issue_status(issue_url: str) -> Optional[str]:
    """Check if an issue is still open by querying the GitHub API."""
    if not issue_url:
        return None
    
    try:
        parts = issue_url.replace("https://github.com/", "").split("/")
        if len(parts) >= 4 and parts[2] == "issues":
            owner, repo, _, issue_number = parts[0], parts[1], parts[2], parts[3]
            api_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{issue_number}"
            
            response = _make_request(api_url)
            if response:
                data = response.json()
                return data.get("state")
    except Exception as e:
        logger.error("check_status_failed", url=issue_url, error=str(e))
    
    return None


def batch_check_issue_status(issue_urls: List[str]) -> Dict[str, str]:
    """Check status of multiple issues efficiently."""
    results = {}
    
    for url in issue_urls:
        status = check_issue_status(url)
        results[url] = status if status else "unknown"
        time.sleep(0.1)
        
        if RATE_LIMIT_REMAINING < 10:
            wait_time = min(RATE_LIMIT_RESET - int(time.time()) + 1, 60)
            if wait_time > 0:
                logger.info("rate_limit_wait", wait_seconds=wait_time)
                time.sleep(wait_time)
    
    return results


def get_repo_metadata_from_api(repo_owner: str, repo_name: str, use_cache: bool = True) -> Optional[Dict]:
    """
    Fetch repository metadata from GitHub API or cache.
    
    When FAST_DISCOVERY=true (default), skips expensive API calls.
    """
    cache_validity = timedelta(days=CACHE_VALIDITY_DAYS)
    
    if use_cache:
        cached = get_repo_metadata(repo_owner, repo_name)
        if cached:
            cached_at = datetime.fromisoformat(cached.get("cached_at", "2000-01-01"))
            if datetime.now() - cached_at < cache_validity:
                return cached
    
    url = f"{GITHUB_API_BASE}/repos/{repo_owner}/{repo_name}"
    response = _make_request(url)
    
    if not response:
        return None
    
    repo_data = response.json()
    
    languages_url = repo_data.get("languages_url", "")
    languages = {}
    if languages_url:
        lang_response = _make_request(languages_url)
        if lang_response:
            languages = lang_response.json()
    
    topics_url = f"{GITHUB_API_BASE}/repos/{repo_owner}/{repo_name}/topics"
    topics = []
    topics_response = _make_request(topics_url, params={"Accept": "application/vnd.github.mercy-preview+json"})
    if topics_response:
        topics_data = topics_response.json()
        topics = topics_data.get("names", [])
    
    last_commit_date = None
    contributor_count = None
    
    if not FAST_DISCOVERY:
        commits_url = f"{GITHUB_API_BASE}/repos/{repo_owner}/{repo_name}/commits"
        commits_response = _make_request(commits_url, params={"per_page": 1})
        if commits_response:
            commits = commits_response.json()
            if commits and len(commits) > 0:
                commit = commits[0]
                last_commit_date = commit.get("commit", {}).get("author", {}).get("date")
        
        contributors_url = f"{GITHUB_API_BASE}/repos/{repo_owner}/{repo_name}/contributors"
        contributors_response = _make_request(contributors_url, params={"per_page": 1, "anon": "true"})
        if contributors_response:
            link_header = contributors_response.headers.get("Link", "")
            if link_header:
                import re
                for link in link_header.split(","):
                    if 'rel="last"' in link:
                        match = re.search(r'page=(\d+)', link)
                        if match:
                            contributor_count = int(match.group(1)) * 100
            else:
                contributors = contributors_response.json()
                contributor_count = len(contributors) if isinstance(contributors, list) else None
    else:
        pushed_at = repo_data.get("pushed_at")
        if pushed_at:
            last_commit_date = pushed_at
    
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
