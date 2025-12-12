"""Developer profile repository."""

from datetime import datetime, timezone

from core.models import DevProfile

from .base import BaseRepository


class ProfileRepository(BaseRepository[DevProfile]):
    """Repository for DevProfile operations."""

    model = DevProfile

    def get_by_user_id(self, user_id: int) -> DevProfile | None:
        """Get profile by user ID."""
        return self.session.query(DevProfile).filter(DevProfile.user_id == user_id).first()

    def create_or_update(
        self,
        user_id: int,
        skills: list[str] | None = None,
        experience_level: str | None = None,
        interests: list[str] | None = None,
        preferred_languages: list[str] | None = None,
        time_availability_hours_per_week: int | None = None,
    ) -> DevProfile:
        """
        Create or update a user's profile.
        Only updates fields that are provided (not None).
        """
        profile = self.get_by_user_id(user_id)

        if profile:
            if skills is not None:
                profile.skills = skills
            if experience_level is not None:
                profile.experience_level = experience_level
            if interests is not None:
                profile.interests = interests
            if preferred_languages is not None:
                profile.preferred_languages = preferred_languages
            if time_availability_hours_per_week is not None:
                profile.time_availability_hours_per_week = time_availability_hours_per_week
            profile.updated_at = datetime.now(timezone.utc)
        else:
            profile = DevProfile(
                user_id=user_id,
                skills=skills or [],
                experience_level=experience_level or "beginner",
                interests=interests or [],
                preferred_languages=preferred_languages or [],
                time_availability_hours_per_week=time_availability_hours_per_week,
            )
            self.session.add(profile)

        self.session.flush()
        return profile

    def has_profile(self, user_id: int) -> bool:
        """Check if a user has a profile (efficient exists query)."""
        return self.exists_where(user_id=user_id)
