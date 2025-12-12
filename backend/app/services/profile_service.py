"""
Profile management service functions.
"""

import io
import re
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from core.models import (
    PROFILE_SOURCE_GITHUB,
    PROFILE_SOURCE_MANUAL,
    PROFILE_SOURCE_RESUME,
)
from core.parsing.skill_extractor import analyze_job_text

from ..models import DevProfile, User
from ..schemas import ProfileUpdateRequest


def get_profile(db: Session, user: User) -> DevProfile | None:
    """Fetch the profile for a user, or None if it does not exist."""
    return db.query(DevProfile).filter(DevProfile.user_id == user.id).one_or_none()


def update_profile(
    db: Session,
    user: User,
    payload: ProfileUpdateRequest,
) -> DevProfile:
    """
    Update profile with user-provided data.

    When core profile fields (skills, experience_level, interests, preferred_languages)
    are modified, the profile_source is changed to "manual" to indicate user customization.
    """
    profile = get_profile(db, user)
    is_new_profile = profile is None

    if not profile:
        profile = DevProfile(user_id=user.id)
        profile.profile_source = PROFILE_SOURCE_MANUAL
        db.add(profile)

    # Track if core fields are being modified
    core_fields_modified = False

    if payload.skills is not None:
        profile.skills = payload.skills
        core_fields_modified = True
    if payload.experience_level is not None:
        profile.experience_level = payload.experience_level
        core_fields_modified = True
    if payload.interests is not None:
        profile.interests = payload.interests
        core_fields_modified = True
    if payload.preferred_languages is not None:
        profile.preferred_languages = payload.preferred_languages
        core_fields_modified = True
    if payload.time_availability is not None:
        profile.time_availability_hours_per_week = payload.time_availability
        # Time availability is not a core field, doesn't change source

    # If core fields were modified on an existing profile, mark as manual
    if core_fields_modified and not is_new_profile:
        profile.profile_source = PROFILE_SOURCE_MANUAL

    db.commit()
    db.refresh(profile)
    return profile


def create_profile_from_github(
    db: Session,
    user: User,
    github_username: str | None = None,
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

    # Track source and sync time
    profile.profile_source = PROFILE_SOURCE_GITHUB
    profile.last_github_sync = datetime.now(timezone.utc)

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
        "profile_source": profile.profile_source or PROFILE_SOURCE_MANUAL,
        "last_github_sync": profile.last_github_sync,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def get_profile_source_info(profile: DevProfile) -> dict:
    """Get detailed information about profile source for UI display."""
    return {
        "source": profile.profile_source or PROFILE_SOURCE_MANUAL,
        "is_from_github": profile.is_from_github,
        "is_from_resume": profile.is_from_resume,
        "is_manual": profile.is_manual,
        "last_github_sync": profile.last_github_sync,
        "can_resync_github": True,  # Always allow re-syncing
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
        r"(\d+)\+?\s*years?\s*(?:of\s+)?(?:experience|exp)",
        r"(\d+)\+?\s*yrs?\s*(?:of\s+)?(?:experience|exp)",
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
    skills = list({skill for skill, _ in skills_with_categories})[:20]

    # Determine experience level from resume text
    experience_level = _determine_experience_level(resume_text)

    # Extract programming languages (common ones)
    programming_languages = [
        "Python",
        "JavaScript",
        "TypeScript",
        "Java",
        "C++",
        "C#",
        "Go",
        "Rust",
        "Ruby",
        "PHP",
        "Swift",
        "Kotlin",
        "Scala",
        "R",
        "MATLAB",
        "Perl",
    ]
    preferred_languages = [
        lang for lang in programming_languages if lang.lower() in resume_text.lower()
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

    # Track source (resume replaces any previous source)
    profile.profile_source = PROFILE_SOURCE_RESUME
    # Clear GitHub sync time since this is now a resume-based profile
    profile.last_github_sync = None

    db.commit()
    db.refresh(profile)
    return profile
