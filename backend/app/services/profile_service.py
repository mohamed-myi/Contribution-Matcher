"""
Profile management service functions.
"""

import io
import re
from typing import Optional

import httpx

from sqlalchemy.orm import Session

from core.parsing.skill_extractor import analyze_job_text

from ..models import DevProfile, User
from ..schemas import ProfileUpdateRequest


def get_profile(db: Session, user: User) -> DevProfile | None:
    return db.query(DevProfile).filter(DevProfile.user_id == user.id).one_or_none()


def update_profile(
    db: Session,
    user: User,
    payload: ProfileUpdateRequest,
) -> DevProfile:
    profile = get_profile(db, user)
    if not profile:
        profile = DevProfile(user_id=user.id)
        db.add(profile)

    if payload.skills is not None:
        profile.skills = payload.skills
    if payload.experience_level is not None:
        profile.experience_level = payload.experience_level
    if payload.interests is not None:
        profile.interests = payload.interests
    if payload.preferred_languages is not None:
        profile.preferred_languages = payload.preferred_languages
    if payload.time_availability is not None:
        profile.time_availability_hours_per_week = payload.time_availability

    db.commit()
    db.refresh(profile)
    return profile


def create_profile_from_github(
    db: Session,
    user: User,
    github_username: Optional[str] = None,
) -> DevProfile:
    """Create or update profile by fetching data from GitHub."""
    username = github_username or user.github_username
    
    # Fetch user's repos to extract languages/skills
    languages = set()
    topics = set()
    
    try:
        with httpx.Client(timeout=30) as client:
            # Fetch user's repos
            repos_resp = client.get(
                f"https://api.github.com/users/{username}/repos",
                params={"per_page": 100, "sort": "updated"},
                headers={"Accept": "application/vnd.github+json"},
            )
            if repos_resp.status_code == 200:
                repos = repos_resp.json()
                for repo in repos:
                    if repo.get("language"):
                        languages.add(repo["language"])
                    if repo.get("topics"):
                        topics.update(repo["topics"])
    except Exception:
        pass  # Use empty sets if GitHub API fails

    profile = get_profile(db, user)
    if not profile:
        profile = DevProfile(user_id=user.id)
        db.add(profile)

    # Set skills from languages and topics
    profile.skills = list(languages)[:20]  # Limit to 20 skills
    profile.interests = list(topics)[:10]  # Limit to 10 interests
    profile.preferred_languages = list(languages)[:10]
    profile.experience_level = profile.experience_level or "intermediate"
    profile.time_availability_hours_per_week = profile.time_availability_hours_per_week or 10

    db.commit()
    db.refresh(profile)
    return profile


def serialize_profile(profile: DevProfile) -> dict:
    """Convert a DevProfile ORM object to a dict."""
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "skills": profile.skills or [],
        "experience_level": profile.experience_level,
        "interests": profile.interests or [],
        "preferred_languages": profile.preferred_languages or [],
        "time_availability": profile.time_availability_hours_per_week,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def _extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF file content."""
    import PyPDF2
    
    pdf_file = io.BytesIO(file_content)
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    
    text_parts = []
    for page in pdf_reader.pages:
        text = page.extract_text()
        if text:
            text_parts.append(text)
    
    return "\n".join(text_parts)


def _determine_experience_level(resume_text: str) -> str:
    """Determine experience level from resume text."""
    exp_patterns = [
        r'(\d+)\+?\s*years?\s*(?:of\s+)?(?:experience|exp)',
        r'(\d+)\+?\s*yrs?\s*(?:of\s+)?(?:experience|exp)',
    ]
    
    experience_years = None
    for pattern in exp_patterns:
        match = re.search(pattern, resume_text.lower())
        if match:
            try:
                experience_years = int(match.group(1))
                break
            except (ValueError, IndexError):
                pass
    
    if experience_years is None:
        return "intermediate"
    elif experience_years < 2:
        return "beginner"
    elif experience_years < 5:
        return "intermediate"
    elif experience_years < 10:
        return "advanced"
    else:
        return "expert"


def create_profile_from_resume(
    db: Session,
    user: User,
    file_content: bytes,
) -> DevProfile:
    """Create or update profile by parsing a resume PDF."""
    # Extract text from PDF
    resume_text = _extract_text_from_pdf(file_content)
    
    # Extract skills using skill extractor
    category, skills_with_categories, _ = analyze_job_text(resume_text)
    
    # Get just the skill names
    skills = list(set(skill for skill, _ in skills_with_categories))[:20]
    
    # Determine experience level from resume text
    experience_level = _determine_experience_level(resume_text)
    
    # Extract programming languages (common ones)
    programming_languages = [
        "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust",
        "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB", "Perl"
    ]
    preferred_languages = [
        lang for lang in programming_languages
        if lang.lower() in resume_text.lower()
    ][:10]
    
    # Get or create profile
    profile = get_profile(db, user)
    if not profile:
        profile = DevProfile(user_id=user.id)
        db.add(profile)
    
    # Update profile with extracted data
    profile.skills = skills
    profile.experience_level = experience_level
    profile.preferred_languages = preferred_languages
    profile.interests = profile.interests or []  # Keep existing interests
    profile.time_availability_hours_per_week = profile.time_availability_hours_per_week or 10
    
    db.commit()
    db.refresh(profile)
    return profile
