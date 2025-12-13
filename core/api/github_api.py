"""GitHub API client with rate limiting and caching."""

import threading
import time
from datetime import datetime, timedelta, timezone

import requests  # type: ignore[import-untyped]

from core.config import get_settings
from core.constants import DISCOVERY_LABELS, GITHUB_API_BASE, GITHUB_GRAPHQL_ENDPOINT
from core.logging import get_logger

logger = get_logger("github")

# Rate limit state (module-level for simplicity)
_rate_limit = {"remaining": 5000, "reset": 0}
_rate_limit_lock = threading.Lock()


def _get_token() -> str | None:
    """Get GitHub token from settings."""
    return get_settings().pat_token


def _get_headers(graphql: bool = False) -> dict[str, str]:
    """Get headers for GitHub API requests."""
    token = _get_token()
    headers = {
        "Accept": "application/json" if graphql else "application/vnd.github.v3+json",
        "User-Agent": "ContributionMatcher/1.0",
    }
    if token:
        prefix = "bearer" if graphql else "token"
        headers["Authorization"] = f"{prefix} {token}"
    return headers


def _update_rate_limit(response: requests.Response) -> None:
    """Update rate limit tracking from response headers."""
    if "X-RateLimit-Remaining" in response.headers:
        with _rate_limit_lock:
            _rate_limit["remaining"] = int(response.headers["X-RateLimit-Remaining"])
            _rate_limit["reset"] = int(response.headers.get("X-RateLimit-Reset", 0))


def _wait_for_rate_limit(max_wait: int = 300) -> bool:
    """Pause when remaining GitHub rate limit is low."""
    with _rate_limit_lock:
        remaining = _rate_limit["remaining"]
        reset = _rate_limit["reset"]

    if remaining >= 10:
        return True

    if reset > 0:
        wait_time = min(reset - int(time.time()) + 1, max_wait)
        if wait_time > 0:
            logger.info("rate_limit_wait", wait_seconds=wait_time, remaining=remaining)
            time.sleep(wait_time)
            return True
    return False


def _make_request(
    url: str,
    params: dict | None = None,
    timeout: int = 30,
    _retry: bool = True,
) -> requests.Response | None:
    """Make a GitHub API request with rate limiting and error handling."""
    token = _get_token()
    if not token:
        logger.warning("no_token", message="PAT_TOKEN not set, using unauthenticated requests")

    _wait_for_rate_limit()

    try:
        response = requests.get(url, headers=_get_headers(), params=params, timeout=timeout)
        _update_rate_limit(response)

        if response.status_code == 200:
            return response
        elif response.status_code == 404:
            logger.debug("api_not_found", url=url)
        elif response.status_code == 401:
            logger.error("api_auth_failed", url=url)
        elif response.status_code == 403:
            # Rate limited - wait and retry once (guarded to prevent recursion loops)
            with _rate_limit_lock:
                reset = _rate_limit["reset"]

            if _retry and reset > 0:
                wait_time = min(reset - int(time.time()) + 1, 300)
                if wait_time > 0:
                    logger.info("rate_limited_retry", wait_seconds=wait_time)
                    time.sleep(wait_time)
                    return _make_request(url, params, timeout, _retry=False)
            logger.error("rate_limited_no_reset")
        else:
            logger.error("api_error", status=response.status_code, url=url)
    except requests.RequestException as e:
        logger.error("request_exception", error=str(e), url=url)

    return None


def _graphql_batch_fetch_repos(
    repo_list: list[tuple[str, str]],
) -> dict[tuple[str, str], dict | None]:
    """
    Fetch metadata for multiple repositories via a single GraphQL query.

    Args:
        repo_list: List of (owner, name) repository tuples.

    Returns:
        Mapping of (owner, name) to repository metadata or None on failure.
    """
    token = _get_token()
    if not token:
        logger.warning("graphql_auth_required")
        return {}

    if not repo_list:
        return {}

    results: dict[tuple[str, str], dict | None] = {}
    chunk_size = 50

    for chunk_start in range(0, len(repo_list), chunk_size):
        chunk = repo_list[chunk_start : chunk_start + chunk_size]

        # Build GraphQL query using variables (avoid string interpolation / injection).
        variable_defs: list[str] = []
        variables: dict[str, str] = {}
        query_parts = []
        for i, (owner, name) in enumerate(chunk):
            owner_var = f"owner{i}"
            name_var = f"name{i}"
            variable_defs.append(f"${owner_var}: String!")
            variable_defs.append(f"${name_var}: String!")
            variables[owner_var] = owner
            variables[name_var] = name
            query_parts.append(
                f"""
                repo_{i}: repository(owner: ${owner_var}, name: ${name_var}) {{
                    owner {{ login }}
                    name
                    stargazerCount
                    forkCount
                    languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{
                        edges {{ size node {{ name }} }}
                    }}
                    repositoryTopics(first: 10) {{
                        nodes {{ topic {{ name }} }}
                    }}
                    defaultBranchRef {{
                        target {{ ... on Commit {{ committedDate }} }}
                    }}
                }}
            """
            )

        query = f"query({', '.join(variable_defs)}) {{ " + " ".join(query_parts) + " }"

        try:
            response = requests.post(
                GITHUB_GRAPHQL_ENDPOINT,
                headers=_get_headers(graphql=True),
                json={"query": query, "variables": variables},
                timeout=60,
            )

            if response.status_code == 200:
                data = response.json()

                if "errors" in data:
                    for error in data.get("errors", []):
                        if "NOT_FOUND" not in str(error.get("type", "")):
                            logger.warning("graphql_error", error=error.get("message", "Unknown"))

                repo_data = data.get("data", {})

                for i, (owner, name) in enumerate(chunk):
                    repo_info = repo_data.get(f"repo_{i}")

                    if repo_info:
                        # Parse languages
                        languages = {
                            edge.get("node", {}).get("name", ""): edge.get("size", 0)
                            for edge in repo_info.get("languages", {}).get("edges", [])
                            if edge.get("node", {}).get("name")
                        }

                        # Parse topics
                        topics = [
                            node.get("topic", {}).get("name", "")
                            for node in repo_info.get("repositoryTopics", {}).get("nodes", [])
                            if node.get("topic", {}).get("name")
                        ]

                        # Parse last commit date
                        last_commit_date = None
                        default_branch = repo_info.get("defaultBranchRef")
                        if default_branch:
                            last_commit_date = default_branch.get("target", {}).get("committedDate")

                        results[(owner, name)] = {
                            "repo_owner": owner,
                            "repo_name": name,
                            "stars": repo_info.get("stargazerCount"),
                            "forks": repo_info.get("forkCount"),
                            "languages": languages,
                            "topics": topics,
                            "last_commit_date": last_commit_date,
                            "contributor_count": None,
                        }
                    else:
                        results[(owner, name)] = None

            elif response.status_code == 403:
                logger.warning("graphql_rate_limited", status=response.status_code)
                _wait_for_rate_limit()
                break
            else:
                logger.error("graphql_request_failed", status=response.status_code)

        except requests.RequestException as e:
            logger.error("graphql_exception", error=str(e))

        # Small delay between chunks
        if chunk_start + chunk_size < len(repo_list):
            time.sleep(0.2)

    return results


def search_issues(
    labels: list[str] | None = None,
    language: str | None = None,
    min_stars: int | None = None,
    limit: int = 100,
    apply_quality_filters: bool = True,
    use_expanded_labels: bool = True,
) -> list[dict]:
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
        List of issue dictionaries from GitHub API
    """
    if labels is None:
        labels = (
            DISCOVERY_LABELS[:8] if use_expanded_labels else ["good first issue", "help wanted"]
        )

    if apply_quality_filters and min_stars is None:
        min_stars = 10

    logger.info(
        "search_started", labels=labels[:5], language=language, min_stars=min_stars, limit=limit
    )

    all_issues: list[dict] = []
    seen_urls: set = set()

    for label in labels:
        if len(all_issues) >= limit:
            break

        page = 1
        per_page = min(100, limit - len(all_issues))

        while len(all_issues) < limit:
            # Build query
            label_query = f'label:"{label}"' if " " in label else f"label:{label}"
            query_parts = [label_query, "state:open"]
            if language:
                query_parts.append(f"language:{language}")

            params = {
                "q": " ".join(query_parts),
                "sort": "updated",
                "order": "desc",
                "per_page": per_page,
                "page": page,
            }

            response = _make_request(f"{GITHUB_API_BASE}/search/issues", params)

            if not response:
                break

            data = response.json()
            items = data.get("items", [])

            if not items:
                break

            for item in items:
                issue_url = item.get("html_url", "")
                if issue_url in seen_urls:
                    continue

                all_issues.append(item)
                seen_urls.add(issue_url)

                if len(all_issues) >= limit:
                    break

            if len(items) < per_page:
                break

            page += 1
            time.sleep(0.5)

    logger.info("search_complete", issues_found=len(all_issues))
    return all_issues[:limit]


def batch_get_repo_metadata(
    repo_list: list[tuple[str, str]],
    use_cache: bool = True,
    batch_size: int = 50,
    use_graphql: bool = True,
) -> dict[tuple[str, str], dict | None]:
    """
    Batch fetch repository metadata for multiple repositories.
    Uses GraphQL by default for efficiency (1 call instead of 5 per repo).

    Args:
        repo_list: List of (owner, name) tuples
        use_cache: Check database cache first
        batch_size: GraphQL batch size
        use_graphql: Use GraphQL API (more efficient)

    Returns:
        Dictionary mapping (owner, name) to metadata dict
    """
    results: dict[tuple[str, str], dict | None] = {}
    settings = get_settings()
    cache_validity = timedelta(days=settings.cache_validity_days)

    # Check cache first
    if use_cache:
        from core.db import db
        from core.repositories import RepoMetadataRepository

        if db.is_initialized:
            with db.session() as session:
                repo_repo = RepoMetadataRepository(session)
                cached = repo_repo.batch_get(repo_list)

                for key, metadata in cached.items():
                    if (
                        metadata
                        and metadata.cached_at
                        and (
                            datetime.now(timezone.utc)
                            - (
                                metadata.cached_at.replace(tzinfo=timezone.utc)
                                if metadata.cached_at.tzinfo is None
                                else metadata.cached_at.astimezone(timezone.utc)
                            )
                            < cache_validity
                        )
                    ):
                        results[key] = metadata.to_dict()

    # Fetch remaining from API
    remaining = [key for key in repo_list if key not in results]

    if not remaining:
        return results

    logger.info("batch_fetch_metadata", repo_count=len(remaining))

    if use_graphql and _get_token():
        graphql_results = _graphql_batch_fetch_repos(remaining)

        # Cache results
        if graphql_results:
            _cache_repo_metadata(graphql_results)

        results.update(graphql_results)
        remaining = [key for key in remaining if key not in results or results.get(key) is None]

    # Fallback to REST API for remaining
    if remaining:
        logger.info("rest_fallback", repo_count=len(remaining))
        for owner, name in remaining:
            metadata = get_repo_metadata_from_api(owner, name, use_cache=False)  # type: ignore[assignment]
            results[(owner, name)] = metadata  # type: ignore[assignment]
            time.sleep(0.1)

    return results


def _cache_repo_metadata(metadata_dict: dict[tuple[str, str], dict | None]) -> None:
    """Cache fetched metadata to database."""
    from core.db import db
    from core.repositories import RepoMetadataRepository

    if not db.is_initialized:
        return

    try:
        with db.session() as session:
            repo_repo = RepoMetadataRepository(session)
            for (owner, name), metadata in metadata_dict.items():
                if metadata:
                    repo_repo.upsert(
                        repo_owner=owner,
                        repo_name=name,
                        stars=metadata.get("stars"),
                        forks=metadata.get("forks"),
                        languages=metadata.get("languages"),
                        topics=metadata.get("topics"),
                        last_commit_date=metadata.get("last_commit_date"),
                        contributor_count=metadata.get("contributor_count"),
                    )
    except Exception as e:
        logger.warning("cache_metadata_failed", error=str(e))


def get_repo_metadata_from_api(
    repo_owner: str, repo_name: str, use_cache: bool = True
) -> dict | None:
    """Fetch repository metadata from GitHub API or cache."""
    settings = get_settings()

    # Check cache first
    if use_cache:
        from core.db import db
        from core.repositories import RepoMetadataRepository

        if db.is_initialized:
            with db.session() as session:
                repo_repo = RepoMetadataRepository(session)
                cached = repo_repo.get_fresh(repo_owner, repo_name, settings.cache_validity_days)
                if cached:
                    return cached.to_dict()

    # Fetch from API
    url = f"{GITHUB_API_BASE}/repos/{repo_owner}/{repo_name}"
    response = _make_request(url)

    if not response:
        return None

    repo_data = response.json()

    # Fetch languages
    languages = {}
    if repo_data.get("languages_url"):
        lang_response = _make_request(repo_data["languages_url"])
        if lang_response:
            languages = lang_response.json()

    # Fetch topics
    topics = []
    topics_response = _make_request(
        f"{GITHUB_API_BASE}/repos/{repo_owner}/{repo_name}/topics",
        params={"Accept": "application/vnd.github.mercy-preview+json"},
    )
    if topics_response:
        topics = topics_response.json().get("names", [])

    # Use pushed_at as last commit date (fast mode)
    last_commit_date = repo_data.get("pushed_at") if settings.fast_discovery else None

    metadata = {
        "repo_owner": repo_owner,
        "repo_name": repo_name,
        "stars": repo_data.get("stargazers_count"),
        "forks": repo_data.get("forks_count"),
        "languages": languages,
        "topics": topics,
        "last_commit_date": last_commit_date,
        "contributor_count": None,
    }

    # Cache the result
    _cache_repo_metadata({(repo_owner, repo_name): metadata})

    return metadata


def check_issue_status(issue_url: str) -> str | None:
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
                state = response.json().get("state")
                return str(state) if state is not None else None
    except Exception as e:
        logger.error("check_status_failed", url=issue_url, error=str(e))

    return None


def batch_check_issue_status(issue_urls: list[str]) -> dict[str, str]:
    """Check status of multiple issues. Uses REST API with batching."""
    results = {}

    for url in issue_urls:
        status = check_issue_status(url)
        results[url] = status if status else "unknown"
        time.sleep(0.1)

        with _rate_limit_lock:
            remaining = _rate_limit["remaining"]
        if remaining < 10:
            _wait_for_rate_limit(max_wait=60)

    return results
