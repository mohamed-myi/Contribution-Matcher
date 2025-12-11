"""
Profile management endpoints.

Refactored to use:
- Core repositories for database access
- Cache invalidation on profile updates
- Celery tasks for background score recomputation
- Secure file upload with MIME validation
"""

import re

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.cache import CacheKeys, cache
from core.logging import get_logger
from core.repositories import ProfileRepository

from ..auth.dependencies import get_current_user, validate_csrf
from ..database import get_db
from ..models import DevProfile, User
from ..schemas import ProfileResponse, ProfileUpdateRequest
from ..services import profile_service

logger = get_logger("profile")

router = APIRouter(prefix="/profile", tags=["profile"])


# =============================================================================
# File Upload Security
# =============================================================================

# Allowed MIME types for resume upload
ALLOWED_MIME_TYPES = {
    "application/pdf",
}

# Maximum file size (5MB)
MAX_FILE_SIZE = 5 * 1024 * 1024

# Regex for sanitizing filenames (remove dangerous characters)
SAFE_FILENAME_PATTERN = re.compile(r"[^a-zA-Z0-9._-]")


def _validate_upload_file(file: UploadFile, content: bytes) -> None:
    """
    Validate uploaded file for security.

    Checks:
    1. File extension matches allowed types
    2. MIME type from content-type header
    3. File size within limits
    4. Magic bytes (PDF signature) validation

    Raises:
        HTTPException: If validation fails
    """
    # Check filename extension
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported. Please upload a .pdf file.",
        )

    # Check MIME type from content-type header
    content_type = file.content_type or ""
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        logger.warning(
            "upload_invalid_mime",
            content_type=content_type,
            filename=filename[:50],  # Truncate for logging
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {content_type}. Only PDF files are supported.",
        )

    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size must be less than {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    # Check PDF magic bytes (PDF files start with %PDF-)
    if len(content) < 5 or not content[:5].startswith(b"%PDF-"):
        logger.warning(
            "upload_invalid_magic_bytes",
            filename=filename[:50],
            first_bytes=content[:10].hex() if content else "empty",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PDF file. The file does not appear to be a valid PDF.",
        )


def _sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and other attacks.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for filesystem operations
    """
    if not filename:
        return "upload.pdf"

    # Remove path components (prevent path traversal)
    filename = filename.replace("\\", "/").split("/")[-1]

    # Remove dangerous characters
    filename = SAFE_FILENAME_PATTERN.sub("_", filename)

    # Limit length
    if len(filename) > 100:
        filename = filename[:100]

    # Ensure .pdf extension
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    return filename


class GitHubProfileRequest(BaseModel):
    github_username: str | None = None


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
        # Celery not available
        pass
    except Exception:
        # Redis/broker connection failed - silently skip in non-critical path
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


@router.post("", response_model=ProfileResponse, dependencies=[Depends(validate_csrf)])
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


@router.post("/from-github", response_model=ProfileResponse, dependencies=[Depends(validate_csrf)])
def create_profile_from_github(
    payload: GitHubProfileRequest | None = None,
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


@router.put("", response_model=ProfileResponse, dependencies=[Depends(validate_csrf)])
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


@router.delete("", dependencies=[Depends(validate_csrf)])
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


@router.post("/from-resume", response_model=ProfileResponse, dependencies=[Depends(validate_csrf)])
async def create_profile_from_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create or update profile by parsing a resume PDF.

    Security:
    - Validates file extension, MIME type, and PDF magic bytes
    - Enforces file size limit (5MB)
    - Sanitizes filename to prevent path traversal

    Extracts skills, experience level, and interests from resume.
    """
    # Read file content first for validation
    content = await file.read()

    # Comprehensive security validation
    _validate_upload_file(file, content)

    # Sanitize filename for logging (not stored, but good practice)
    safe_filename = _sanitize_filename(file.filename or "resume.pdf")
    logger.info(
        "resume_upload_validated",
        user_id=current_user.id,
        filename=safe_filename,
        size_bytes=len(content),
    )

    try:
        profile = profile_service.create_profile_from_resume(db, current_user, content)
    except Exception as e:
        logger.warning(
            "resume_parse_failed",
            user_id=current_user.id,
            error=str(e),
        )
        # Generic error message - don't expose parsing details
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to parse resume. Please ensure the PDF contains readable text.",
        )

    # Trigger cache invalidation and score recomputation
    _invalidate_user_cache(current_user.id)
    _trigger_score_recomputation(current_user.id)

    return _profile_to_response(profile)


@router.post("/recompute-scores", dependencies=[Depends(validate_csrf)])
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
