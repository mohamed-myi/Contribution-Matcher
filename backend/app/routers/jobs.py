"""
Job management endpoints for the internal scheduler.

Security:
- All endpoints require authentication
- Rate limiting is applied to prevent abuse
"""

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth.dependencies import get_current_user
from ..config import get_settings
from ..dependencies.rate_limit import enforce_rate_limit
from ..models import User
from ..scheduler import list_jobs, reschedule_job, trigger_job
from ..schemas import JobInfo, JobRescheduleRequest, JobRunRequest

# Router requires both authentication and rate limiting
router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    dependencies=[Depends(enforce_rate_limit)],
)


def _ensure_scheduler_enabled():
    """Abort if internal scheduler is disabled in configuration."""
    if not get_settings().enable_scheduler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal scheduler is disabled",
        )


@router.get("", response_model=list[JobInfo])
def get_jobs(current_user: User = Depends(get_current_user)):
    """
    List all scheduled jobs.

    Requires authentication.
    """
    _ensure_scheduler_enabled()
    return list_jobs()


@router.post("/run")
def run_job(
    request: JobRunRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger a scheduled job.

    Requires authentication. The job will run with the current user's context
    if user_id is not specified in the request.
    """
    _ensure_scheduler_enabled()
    try:
        # Use current user's ID if not specified in request
        user_id = request.user_id if request.user_id else current_user.id
        trigger_job(request.job_id, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"status": "scheduled", "user_id": user_id}


@router.post("/reschedule")
def update_schedule(
    request: JobRescheduleRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Update the schedule for a job.

    Requires authentication.
    """
    _ensure_scheduler_enabled()
    try:
        reschedule_job(request.job_id, request.cron)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"status": "updated"}
