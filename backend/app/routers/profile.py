"""
Profile management endpoints.

Refactored to use:
- Core repositories for database access
- Cache invalidation on profile updates
- Celery tasks for background score recomputation
"""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.repositories import ProfileRepository
from core.cache import cache, CacheKeys

from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models import User, DevProfile
from ..schemas import ProfileResponse, ProfileUpdateRequest
from ..services import profile_service

router = APIRouter(prefix="/profile", tags=["profile"])


class GitHubProfileRequest(BaseModel):
    github_username: Optional[str] = None


def _profile_to_response(profile: DevProfile) -> ProfileResponse:
    """Convert DevProfile to response."""
    return ProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        skills=profile.skills or [],
        experience_level=profile.experience_level,
        interests=profile.interests or [],
        preferred_languages=profile.preferred_languages or [],
        time_availability=profile.time_availability_hours_per_week,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _invalidate_user_cache(user_id: int):
    """Invalidate all cached data for a user when profile changes."""
    cache.delete_pattern(CacheKeys.user_pattern(user_id))


def _trigger_score_recomputation(user_id: int):
    """Trigger background score recomputation after profile update."""
    try:
        from workers.tasks import on_profile_update_task
        on_profile_update_task.delay(user_id)
    except ImportError:
        # Celery not available, just invalidate cache
        pass


@router.get("", response_model=ProfileResponse)
def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's profile."""
    repo = ProfileRepository(db)
    profile = repo.get_by_user_id(current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Create one using POST /profile or POST /profile/from-github",
        )
    
    return _profile_to_response(profile)


@router.post("", response_model=ProfileResponse)
def create_profile(
    payload: ProfileUpdateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new profile manually."""
    repo = ProfileRepository(db)
    
    # Check if profile already exists
    existing = repo.get_by_user_id(current_user.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile already exists. Use PUT /profile to update.",
        )
    
    # Create profile
    profile = repo.create_or_update(
        user_id=current_user.id,
        skills=payload.skills,
        experience_level=payload.experience_level,
        interests=payload.interests,
        preferred_languages=payload.preferred_languages,
        time_availability_hours_per_week=payload.time_availability,
    )
    db.commit()
    
    return _profile_to_response(profile)


@router.post("/from-github", response_model=ProfileResponse)
def create_profile_from_github(
    payload: GitHubProfileRequest = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create or update profile by fetching data from GitHub.
    
    Analyzes repositories, languages, and contribution patterns.
    """
    username = payload.github_username if payload else None
    profile = profile_service.create_profile_from_github(db, current_user, username)
    
    # Trigger cache invalidation and score recomputation
    _invalidate_user_cache(current_user.id)
    _trigger_score_recomputation(current_user.id)
    
    return _profile_to_response(profile)


@router.put("", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update existing profile.
    
    Triggers cache invalidation and score recomputation.
    """
    repo = ProfileRepository(db)
    
    # Update using repository
    profile = repo.create_or_update(
        user_id=current_user.id,
        skills=payload.skills,
        experience_level=payload.experience_level,
        interests=payload.interests,
        preferred_languages=payload.preferred_languages,
        time_availability_hours_per_week=payload.time_availability,
    )
    db.commit()
    
    # Trigger cache invalidation and score recomputation in background
    background_tasks.add_task(_invalidate_user_cache, current_user.id)
    background_tasks.add_task(_trigger_score_recomputation, current_user.id)
    
    return _profile_to_response(profile)


@router.delete("")
def delete_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete user's profile."""
    repo = ProfileRepository(db)
    profile = repo.get_by_user_id(current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    
    db.delete(profile)
    db.commit()
    
    # Invalidate cache
    _invalidate_user_cache(current_user.id)
    
    return {"status": "deleted"}


@router.post("/from-resume", response_model=ProfileResponse)
async def create_profile_from_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create or update profile by parsing a resume PDF.
    
    Extracts skills, experience level, and interests from resume.
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported",
        )
    
    # Read file content
    content = await file.read()
    
    # Limit file size (5MB)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 5MB",
        )
    
    try:
        profile = profile_service.create_profile_from_resume(db, current_user, content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse resume: {str(e)}",
        )
    
    # Trigger cache invalidation and score recomputation
    _invalidate_user_cache(current_user.id)
    _trigger_score_recomputation(current_user.id)
    
    return _profile_to_response(profile)


@router.post("/recompute-scores")
def recompute_scores(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger score recomputation for all issues.
    
    Useful after profile changes or ML model updates.
    """
    try:
        from workers.tasks import score_user_issues_task
        
        task = score_user_issues_task.delay(current_user.id)
        
        return {
            "task_id": task.id,
            "status": "recomputation_queued",
            "message": "Score recomputation started. This may take a few minutes.",
        }
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background workers not available. Try again later.",
        )
