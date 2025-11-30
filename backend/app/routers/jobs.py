"""
Job management endpoints for the internal scheduler.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from ..config import get_settings
from ..dependencies.rate_limit import enforce_rate_limit
from ..scheduler import list_jobs, reschedule_job, trigger_job
from ..schemas import JobInfo, JobRescheduleRequest, JobRunRequest

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(enforce_rate_limit)])


def _ensure_scheduler_enabled():
    if not get_settings().enable_scheduler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal scheduler is disabled",
        )


@router.get("", response_model=list[JobInfo])
def get_jobs():
    _ensure_scheduler_enabled()
    return list_jobs()


@router.post("/run")
def run_job(request: JobRunRequest):
    _ensure_scheduler_enabled()
    try:
        trigger_job(request.job_id, user_id=request.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"status": "scheduled"}


@router.post("/reschedule")
def update_schedule(request: JobRescheduleRequest):
    _ensure_scheduler_enabled()
    try:
        reschedule_job(request.job_id, request.cron)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"status": "updated"}

