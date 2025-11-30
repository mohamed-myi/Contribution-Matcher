# Issue scoring module for matching developer profile against GitHub issues

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from core.config import (
    CODE_FOCUSED_TYPES,
    EXPERIENCE_MATCH_WEIGHT,
    FRESHNESS_WEIGHT,
    INTEREST_MATCH_WEIGHT,
    REPO_QUALITY_WEIGHT,
    SKILL_MATCH_WEIGHT,
    TIME_MATCH_WEIGHT,
    TECHNOLOGY_FAMILIES,
    TECHNOLOGY_SYNONYMS,
)
from core.database import get_issue_technologies, query_issues
from core.profile import load_dev_profile
from core.scoring.ml_trainer import predict_issue_quality


def _normalize_tech_name(tech: str) -> str:
    '''
    Normalize technology name for matching.
    
    Returns - Normalized technology name
    '''
    return tech.lower().strip().replace(" ", "-").replace("_", "-")


def _get_tech_variants(tech: str) -> set:
    '''
    Get all variants and synonyms for a technology.
    
    Returns - Set of normalized technology variants
    '''
    normalized = _normalize_tech_name(tech)
    variants = {normalized}
    
    # Add synonyms
    if normalized in TECHNOLOGY_SYNONYMS:
        for synonym in TECHNOLOGY_SYNONYMS[normalized]:
            variants.add(_normalize_tech_name(synonym))
    
    # Add family members
    for family, members in TECHNOLOGY_FAMILIES.items():
        if normalized in [_normalize_tech_name(m) for m in members]:
            for member in members:
                variants.add(_normalize_tech_name(member))
    
    return variants


def _skills_match_semantic(skill1: str, skill2: str) -> bool:
    '''
    Check if two skills match semantically (exact, synonym, or family relationship).
    
    Returns - True if skills match semantically
    '''
    skill1_variants = _get_tech_variants(skill1)
    skill2_variants = _get_tech_variants(skill2)
    
    # Check for overlap in variants
    if skill1_variants & skill2_variants:
        return True
    
    # Check for substring matches (e.g., "react" in "react-native")
    skill1_norm = _normalize_tech_name(skill1)
    skill2_norm = _normalize_tech_name(skill2)
    
    if skill1_norm in skill2_norm or skill2_norm in skill1_norm:
        return True
    
    return False


def calculate_skill_match(user_skills: List[str], tech_stack: List[str]) -> Tuple[float, List[str], List[str]]:
    '''
    Compares user skills with tech stack and calculates match percentage using semantic matching.
    Handles synonyms, technology families, and variations.

    Returns - (match_percentage, matching_skills, missing_skills)
    '''

    if not tech_stack:
        return (100.0, [], [])

    # Find matching skills using semantic matching
    matching_skills = []
    missing_skills = []

    for issue_tech in tech_stack:
        matched = False
        for user_skill in user_skills:
            if _skills_match_semantic(user_skill, issue_tech):
                matching_skills.append(issue_tech)
                matched = True
                break
        if not matched:
            missing_skills.append(issue_tech)

    # Calculate match percentage
    match_percentage = (len(matching_skills) / len(tech_stack)) * 100.0 if tech_stack else 0.0

    return (match_percentage, matching_skills, missing_skills)


def calculate_experience_match(profile_level: str, issue_difficulty: Optional[str]) -> float:
    '''
    Calculate experience level match.

    Returns - Score from 0-20 (20 = perfect match, 0 = mismatch)
    '''

    if not issue_difficulty:
        return 10.0  # Neutral score if no difficulty specified
    
    # Map difficulty to experience
    difficulty_map = {
        "beginner": "beginner",
        "intermediate": "intermediate",
        "advanced": "advanced",
    }
    
    issue_level = difficulty_map.get(issue_difficulty.lower())
    if not issue_level:
        return 10.0
    
    profile_level_lower = profile_level.lower()
    
    if profile_level_lower == issue_level:
        return 20.0  # Perfect match
    
    # Close matches
    if (profile_level_lower == "beginner" and issue_level == "intermediate") or \
       (profile_level_lower == "intermediate" and issue_level == "beginner"):
        return 15.0  # Close match
    
    if (profile_level_lower == "intermediate" and issue_level == "advanced") or \
       (profile_level_lower == "advanced" and issue_level == "intermediate"):
        return 15.0  # Close match
    
    # Mismatches
    if profile_level_lower == "beginner" and issue_level == "advanced":
        return 5.0  # Too difficult
    
    if profile_level_lower == "advanced" and issue_level == "beginner":
        return 10.0  # Overqualified but acceptable
    
    return 10.0  # Default neutral


def calculate_repo_quality(repo_metadata: Optional[Dict]) -> float:
    '''
    Calculate repository quality score.

    Returns - Score from 0-15
    '''

    if not repo_metadata:
        return 5.0  # Neutral if no metadata
    
    score = 0.0
    
    # Active maintenance (0-5 pts)
    last_commit_date = repo_metadata.get("last_commit_date")
    if last_commit_date:
        try:
            commit_date = datetime.fromisoformat(last_commit_date.replace('Z', '+00:00'))
            days_since_commit = (datetime.now(commit_date.tzinfo) - commit_date).days
            
            if days_since_commit <= 30:
                score += 5.0  # Very active
            elif days_since_commit <= 90:
                score += 3.0  # Moderately active
            elif days_since_commit <= 180:
                score += 1.0  # Somewhat active
            # 0 pts if > 180 days
        except (ValueError, AttributeError):
            pass
    
    # Healthy star/fork ratio (0-5 pts)
    stars = repo_metadata.get("stars", 0) or 0
    forks = repo_metadata.get("forks", 0) or 0
    
    if stars > 0:
        fork_ratio = forks / stars if stars > 0 else 0
        if fork_ratio >= 0.1:  # Healthy ratio
            score += 2.5
        if stars >= 100:
            score += 2.5  # Popular repo
        elif stars >= 10:
            score += 1.0  # Somewhat popular
    
    # Contributor community size (0-5 pts)
    contributor_count = repo_metadata.get("contributor_count")
    if contributor_count:
        if contributor_count >= 10:
            score += 5.0
        elif contributor_count >= 5:
            score += 3.0
        elif contributor_count >= 2:
            score += 1.0
    
    return min(15.0, score)


def calculate_freshness(issue_updated_at: Optional[str]) -> float:
    '''
    Calculate issue freshness score.

    Returns - Score from 0-10
    '''

    if not issue_updated_at:
        return 1.0  # Default low score
    
    try:
        updated_date = datetime.fromisoformat(issue_updated_at.replace('Z', '+00:00'))
        days_ago = (datetime.now(updated_date.tzinfo) - updated_date).days
        
        if days_ago <= 7:
            return 10.0  # Recently updated
        elif days_ago <= 30:
            return 7.0
        elif days_ago <= 90:
            return 4.0
        else:
            return 1.0
    except (ValueError, AttributeError):
        return 1.0


def calculate_time_match(profile_availability: Optional[int], issue_time_estimate: Optional[str]) -> float:
    '''
    Calculate time availability match.

    Returns - Score from 0-10
    '''

    if not profile_availability or not issue_time_estimate:
        return 5.0  # Neutral if missing
    
    # Parse time estimate
    hours_estimate = None
    
    # Try to extract hours
    hour_match = re.search(r'(\d+)\s*(?:-\s*(\d+))?\s*(?:hour|hr|hours|hrs)', issue_time_estimate.lower())
    if hour_match:
        if hour_match.group(2):
            # Range: take average
            hours_estimate = (int(hour_match.group(1)) + int(hour_match.group(2))) / 2
        else:
            hours_estimate = int(hour_match.group(1))
    else:
        # Check for days
        day_match = re.search(r'(\d+)\s*(?:-\s*(\d+))?\s*(?:day|days)', issue_time_estimate.lower())
        if day_match:
            if day_match.group(2):
                days = (int(day_match.group(1)) + int(day_match.group(2))) / 2
            else:
                days = int(day_match.group(1))
            hours_estimate = days * 8  # Assume 8 hours per day
        elif "weekend" in issue_time_estimate.lower():
            hours_estimate = 16  # Weekend project ~16 hours
        elif "small" in issue_time_estimate.lower() or "quick" in issue_time_estimate.lower():
            hours_estimate = 2  # Small task ~2 hours
    
    if hours_estimate is None:
        return 5.0  # Can't parse
    
    # Calculate match
    if hours_estimate <= profile_availability:
        return 10.0  # Fits within availability
    elif hours_estimate <= profile_availability * 2:
        return 5.0  # 2x availability - might be doable
    else:
        return 0.0  # Too much time required


def calculate_interest_match(profile_interests: List[str], repo_topics: List[str]) -> float:
    '''
    Calculate interest match based on repo topics.

    Returns - Score from 0-5
    '''

    if not profile_interests or not repo_topics:
        return 2.5  # Neutral if missing
    
    profile_interests_lower = [i.lower() for i in profile_interests]
    repo_topics_lower = [t.lower() for t in repo_topics]
    
    # Count matches
    matches = sum(1 for topic in repo_topics_lower if topic in profile_interests_lower)
    
    if matches == 0:
        return 0.0
    elif matches >= 3:
        return 5.0  # Strong match
    elif matches >= 2:
        return 3.0
    else:
        return 1.0


def get_match_breakdown(profile: Dict, issue_data: Dict) -> Dict:
    '''
    Get detailed breakdown of profile-issue match.

    Returns - Dictionary with detailed match breakdown
    '''

    # Get issue technologies
    issue_id = issue_data.get("id")
    if issue_id:
        issue_techs_tuples = get_issue_technologies(issue_id)
        issue_technologies = [tech for tech, _ in issue_techs_tuples]
    else:
        issue_technologies = []
    
    profile_skills = profile.get("skills", [])
    
    # Calculate skill match
    skill_match_pct, skill_matching, skill_missing = calculate_skill_match(
        profile_skills, issue_technologies
    )
    
    # Calculate other matches
    experience_score = calculate_experience_match(
        profile.get("experience_level", "intermediate"),
        issue_data.get("difficulty")
    )
    
    # Get repo metadata
    repo_metadata = {}
    if issue_data.get("repo_owner") and issue_data.get("repo_name"):
        from core.database import get_repo_metadata
        repo_metadata = get_repo_metadata(issue_data["repo_owner"], issue_data["repo_name"]) or {}
    
    repo_quality_score = calculate_repo_quality(repo_metadata)
    
    freshness_score = calculate_freshness(issue_data.get("updated_at"))
    
    time_match_score = calculate_time_match(
        profile.get("time_availability_hours_per_week"),
        issue_data.get("time_estimate")
    )
    
    interest_match_score = calculate_interest_match(
        profile.get("interests", []),
        issue_data.get("repo_topics", []) if isinstance(issue_data.get("repo_topics"), list) else []
    )
    
    return {
        "skills": {
            "match_percentage": skill_match_pct,
            "matching": skill_matching,
            "missing": skill_missing,
            "total_required": len(issue_technologies),
        },
        "experience": {
            "score": experience_score,
            "profile_level": profile.get("experience_level"),
            "issue_difficulty": issue_data.get("difficulty"),
        },
        "repo_quality": {
            "score": repo_quality_score,
            "stars": repo_metadata.get("stars"),
            "forks": repo_metadata.get("forks"),
            "contributor_count": repo_metadata.get("contributor_count"),
        },
        "freshness": {
            "score": freshness_score,
            "updated_at": issue_data.get("updated_at"),
        },
        "time_match": {
            "score": time_match_score,
            "profile_availability": profile.get("time_availability_hours_per_week"),
            "issue_estimate": issue_data.get("time_estimate"),
        },
        "interest_match": {
            "score": interest_match_score,
            "profile_interests": profile.get("interests", []),
            "repo_topics": issue_data.get("repo_topics", []),
        },
    }


def score_issue_against_profile(profile: Dict, issue_data: Dict) -> Dict:
    '''
    Calculate overall match score for profile against an issue.
    Uses hybrid approach: rule-based scoring adjusted by ML predictions.

    Returns - Dictionary with score and breakdown
    '''

    breakdown = get_match_breakdown(profile, issue_data)
    
    # Calculate weighted score (rule-based)
    skill_score = (breakdown["skills"]["match_percentage"] / 100.0) * SKILL_MATCH_WEIGHT
    experience_score = breakdown["experience"]["score"]
    repo_quality_score = breakdown["repo_quality"]["score"]
    freshness_score = breakdown["freshness"]["score"]
    time_match_score = breakdown["time_match"]["score"]
    interest_match_score = breakdown["interest_match"]["score"]
    
    rule_based_score = (
        skill_score +
        experience_score +
        repo_quality_score +
        freshness_score +
        time_match_score +
        interest_match_score
    )
    
    # Apply code-focused issue type bonus (10% boost for bugs, features, refactoring)
    issue_type = issue_data.get("issue_type", "").lower() if issue_data.get("issue_type") else ""
    if issue_type in CODE_FOCUSED_TYPES:
        rule_based_score = rule_based_score * 1.1
    
    # Get ML prediction
    ml_good_prob, ml_bad_prob = predict_issue_quality(issue_data, profile)
    
    # Adjust score based on ML prediction
    ml_adjustment = 0.0
    if ml_good_prob > 0.7:  # High confidence good
        ml_adjustment = (ml_good_prob - 0.7) * 50.0  # Scale 0.7-1.0 to 0-15
    elif ml_bad_prob > 0.7:  # High confidence bad
        ml_adjustment = -(ml_bad_prob - 0.7) * 50.0  # Scale 0.7-1.0 to 0-15
    
    # Apply ML adjustment (45% weight on ML, 55% on rule-based)
    ml_weight = 0.45
    rule_weight = 0.55
    
    adjusted_score = rule_based_score + (ml_adjustment * ml_weight)
    
    # Clamp to 0-100 range
    adjusted_score = max(0.0, min(100.0, adjusted_score))
    
    # Add ML info to breakdown
    breakdown["ml_prediction"] = {
        "good_probability": round(ml_good_prob, 3),
        "bad_probability": round(ml_bad_prob, 3),
        "adjustment": round(ml_adjustment * ml_weight, 2),
        "rule_based_score": round(rule_based_score, 2),
    }
    
    return {
        "issue_id": issue_data.get("id"),
        "issue_title": issue_data.get("title"),
        "repo_name": issue_data.get("repo_name"),
        "url": issue_data.get("url"),
        "score": round(adjusted_score, 2),
        "breakdown": breakdown,
    }


def score_profile_against_all_issues(
    profile: Optional[Dict] = None,
    issue_ids: Optional[List[int]] = None,
    limit: Optional[int] = None
) -> List[Dict]:
    '''
    Score profile against multiple issues.

    Returns - List of score dictionaries, sorted by score (descending)
    '''

    if profile is None:
        profile = load_dev_profile()
    
    # Query issues
    if issue_ids:
        issues = []
        for issue_id in issue_ids:
            issue_list = query_issues(limit=1)
            for issue in query_issues():
                if issue.get("id") == issue_id:
                    issues.append(issue)
                    break
    else:
        issues = query_issues(limit=limit)
    
    # Score each issue
    scores = []
    for issue in issues:
        try:
            score_result = score_issue_against_profile(profile, issue)
            scores.append(score_result)
        except Exception as e:
            print(f"Error scoring issue {issue.get('id')}: {e}")
            continue
    
    # Sort by score descending
    scores.sort(key=lambda x: x["score"], reverse=True)
    
    return scores


def get_top_matches(
    profile: Optional[Dict] = None,
    limit: int = 10
) -> List[Dict]:
    '''
    Get top N matching issues for profile.

    Returns - List of top scoring issues
    '''

    all_scores = score_profile_against_all_issues(profile=profile)
    return all_scores[:limit]

