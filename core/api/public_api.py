# Public API for programmatic use of Contribution Matcher

from typing import Dict, List, Optional

from core.database import init_db, query_issues
from core.profile import load_dev_profile, save_dev_profile
from core.api.github_api import search_issues, get_repo_metadata_from_api
from core.parsing import parse_issue
from core.parsing.skill_extractor import analyze_job_text
from core.database import upsert_issue, replace_issue_technologies
from core.scoring import (
    score_issue_against_profile,
    score_profile_against_all_issues,
    get_top_matches,
    train_model as train_ml_model,
)


def discover_issues(
    labels: Optional[List[str]] = None,
    language: Optional[str] = None,
    min_stars: Optional[int] = None,
    limit: int = 100,
    apply_quality_filters: bool = True
) -> List[Dict]:
    '''
    Discover and store GitHub issues.
    
    Args:
        labels: List of labels to search for
        language: Programming language filter
        min_stars: Minimum repository stars
        limit: Maximum number of issues to fetch
        apply_quality_filters: Apply default quality filters
        
    Returns:
        List of discovered issue dictionaries
    '''
    init_db()
    
    issues = search_issues(
        labels=labels,
        language=language,
        min_stars=min_stars,
        limit=limit,
        apply_quality_filters=apply_quality_filters
    )
    
    stored_issues = []
    for issue in issues:
        try:
            repo_url = issue.get("repository_url", "")
            repo_owner = None
            repo_name = None
            if repo_url:
                parts = repo_url.replace("https://api.github.com/repos/", "").split("/")
                if len(parts) >= 2:
                    repo_owner, repo_name = parts[0], parts[1]
            
            repo_metadata = None
            if repo_owner and repo_name:
                repo_metadata = get_repo_metadata_from_api(repo_owner, repo_name, use_cache=True)
            
            parsed = parse_issue(issue, repo_metadata)
            issue_body = parsed.get("body", "") or ""
            category, technologies, keyword_counts = analyze_job_text(issue_body)
            
            issue_id = upsert_issue(
                title=parsed.get("title", ""),
                url=parsed.get("url", ""),
                body=parsed.get("body"),
                repo_owner=parsed.get("repo_owner"),
                repo_name=parsed.get("repo_name"),
                repo_url=parsed.get("repo_url"),
                difficulty=parsed.get("difficulty"),
                issue_type=parsed.get("issue_type"),
                time_estimate=parsed.get("time_estimate"),
                labels=parsed.get("labels", []),
                repo_stars=parsed.get("repo_stars"),
                repo_forks=parsed.get("repo_forks"),
                repo_languages=parsed.get("repo_languages"),
                repo_topics=parsed.get("repo_topics"),
                last_commit_date=parsed.get("last_commit_date"),
                contributor_count=parsed.get("contributor_count"),
                is_active=parsed.get("is_active"),
            )
            
            replace_issue_technologies(issue_id, technologies)
            
            stored_issues.append({
                'id': issue_id,
                'title': parsed.get("title", ""),
                'url': parsed.get("url", ""),
            })
        except Exception as e:
            continue
    
    return stored_issues


def score_issue(issue_id: int, profile_path: Optional[str] = None) -> Dict:
    '''
    Score a specific issue against the developer profile.
    
    Args:
        issue_id: ID of the issue to score
        profile_path: Optional path to profile file (default: dev_profile.json)
        
    Returns:
        Dictionary with score and breakdown
    '''
    init_db()
    
    profile = load_dev_profile(profile_path)
    issues = query_issues()
    
    issue = None
    for i in issues:
        if i.get("id") == issue_id:
            issue = i
            break
    
    if not issue:
        raise ValueError(f"Issue with ID {issue_id} not found")
    
    return score_issue_against_profile(profile, issue)


def score_all_issues(
    limit: Optional[int] = None,
    profile_path: Optional[str] = None
) -> List[Dict]:
    '''
    Score all issues against the developer profile.
    
    Args:
        limit: Maximum number of issues to score
        profile_path: Optional path to profile file
        
    Returns:
        List of scored issues sorted by score (descending)
    '''
    init_db()
    
    profile = load_dev_profile(profile_path)
    
    return score_profile_against_all_issues(profile=profile, limit=limit)


def get_top_matches_api(
    limit: int = 10,
    profile_path: Optional[str] = None
) -> List[Dict]:
    '''
    Get top N matching issues for the developer profile.
    
    Args:
        limit: Number of top matches to return
        profile_path: Optional path to profile file
        
    Returns:
        List of top matching issues
    '''
    init_db()
    
    profile = load_dev_profile(profile_path)
    
    return get_top_matches(profile=profile, limit=limit)


def train_model_api(
    force: bool = False,
    use_advanced: bool = True,
    use_stacking: bool = True,
    use_tuning: bool = True,
    tune_iterations: int = 50,
    legacy: bool = False
) -> Dict:
    '''
    Train the ML model.
    
    Args:
        force: Train even with less than 200 labeled issues
        use_advanced: Use advanced features (embeddings, etc.)
        use_stacking: Use stacking ensemble
        use_tuning: Optimize hyperparameters
        tune_iterations: Number of optimization iterations
        legacy: Use legacy GradientBoosting model
        
    Returns:
        Dictionary with training metrics
    '''
    init_db()
    
    return train_ml_model(
        force=force,
        use_advanced=use_advanced,
        use_stacking=use_stacking,
        use_tuning=use_tuning,
        tune_iterations=tune_iterations,
        legacy=legacy
    )


def list_issues(
    difficulty: Optional[str] = None,
    technology: Optional[str] = None,
    repo_owner: Optional[str] = None,
    issue_type: Optional[str] = None,
    days_back: Optional[int] = None,
    limit: Optional[int] = None
) -> List[Dict]:
    '''
    List issues from the database with optional filters.
    
    Args:
        difficulty: Filter by difficulty level
        technology: Filter by technology
        repo_owner: Filter by repository owner
        issue_type: Filter by issue type
        days_back: Only show issues from last N days
        limit: Maximum number of results
        
    Returns:
        List of issue dictionaries
    '''
    init_db()
    
    return query_issues(
        difficulty=difficulty,
        technology=technology,
        repo_owner=repo_owner,
        issue_type=issue_type,
        days_back=days_back,
        limit=limit
    )


def get_profile(profile_path: Optional[str] = None) -> Dict:
    '''
    Load developer profile.
    
    Args:
        profile_path: Optional path to profile file
        
    Returns:
        Profile dictionary
    '''
    return load_dev_profile(profile_path)


def save_profile(profile: Dict, profile_path: Optional[str] = None) -> None:
    '''
    Save developer profile.
    
    Args:
        profile: Profile dictionary
        profile_path: Optional path to profile file
    '''
    save_dev_profile(profile, profile_path)

