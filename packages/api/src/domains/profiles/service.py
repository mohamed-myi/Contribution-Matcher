"""
Profile Service.

Business logic for profile operations.
"""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from core.models import DevProfile
from core.repositories import ProfileRepository


class ProfileService:
    """Service for profile-related business logic."""
    
    def __init__(self, session: Session):
        self.session = session
        self.repository = ProfileRepository(session)
    
    def get_profile(self, user_id: int) -> Optional[DevProfile]:
        """Get user's profile."""
        return self.repository.get_by_user_id(user_id)
    
    def has_profile(self, user_id: int) -> bool:
        """Check if user has a profile."""
        return self.repository.has_profile(user_id)
    
    def create_or_update_profile(
        self,
        user_id: int,
        skills: Optional[List[str]] = None,
        experience_level: Optional[str] = None,
        interests: Optional[List[str]] = None,
        preferred_languages: Optional[List[str]] = None,
        time_availability_hours_per_week: Optional[int] = None,
        source: Optional[str] = None,
    ) -> DevProfile:
        """Create or update a user's profile."""
        profile = self.repository.create_or_update(
            user_id=user_id,
            skills=skills,
            experience_level=experience_level,
            interests=interests,
            preferred_languages=preferred_languages,
            time_availability_hours_per_week=time_availability_hours_per_week,
        )
        
        if source:
            profile.source = source
            self.session.flush()
        
        return profile
    
    def import_from_github(self, user_id: int, github_username: str) -> DevProfile:
        """
        Import profile data from GitHub.
        
        Analyzes repositories and activity to extract skills and interests.
        """
        from core.profile.dev_profile import create_profile_from_github
        
        # Use existing profile creation logic
        profile_data = create_profile_from_github(github_username)
        
        return self.create_or_update_profile(
            user_id=user_id,
            skills=profile_data.get("skills", []),
            experience_level=profile_data.get("experience_level", "intermediate"),
            interests=profile_data.get("interests", []),
            preferred_languages=profile_data.get("preferred_languages", []),
            time_availability_hours_per_week=profile_data.get("time_availability_hours_per_week"),
            source="github",
        )
    
    def import_from_resume(self, user_id: int, resume_content: bytes) -> DevProfile:
        """
        Import profile data from resume.
        
        Parses resume to extract skills and experience.
        """
        from core.profile.dev_profile import create_profile_from_resume_content
        
        # Use existing resume parsing logic
        profile_data = create_profile_from_resume_content(resume_content)
        
        return self.create_or_update_profile(
            user_id=user_id,
            skills=profile_data.get("skills", []),
            experience_level=profile_data.get("experience_level", "intermediate"),
            interests=profile_data.get("interests", []),
            preferred_languages=profile_data.get("preferred_languages", []),
            source="resume",
        )
    
    def to_dict(self, profile: DevProfile) -> Dict:
        """Convert profile to dictionary."""
        return {
            "id": profile.id,
            "user_id": profile.user_id,
            "skills": profile.skills or [],
            "experience_level": profile.experience_level,
            "interests": profile.interests or [],
            "preferred_languages": profile.preferred_languages or [],
            "time_availability_hours_per_week": profile.time_availability_hours_per_week,
            "source": getattr(profile, 'source', None),
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        }
