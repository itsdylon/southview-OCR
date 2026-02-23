"""Job management endpoints."""

import threading

from fastapi import APIRouter, HTTPException

from southview.db.engine import get_session
from southview.db.models import Job, Video
from southview.jobs.manager import create_job
from southview.jobs.runner import run_full_pipeline

router = APIRouter(tags=["jobs"])


@router.post("/jobs/{video_id}/start")
def start_job(video_id: str):
    """Create and start a processing job for a video."""
    session = get_session()
    try:
        video = session.query(Video).get(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
    finally:
        session.close()

    job = create_job(video_id, "full_pipeline")

    # Run in background thread (simple single-machine approach)
    thread = threading.Thread(
        target=run_full_pipeline, args=(job.id, video_id), daemon=True
    )
    thread.start()

    return {"id": job.id, "video_id": video_id, "status": "queued", "job_type": "full_pipeline"}


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    """Get job status and progress."""
    session = get_session()
    try:
        job = session.query(Job).get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "id": job.id,
            "video_id": job.video_id,
            "job_type": job.job_type,
            "status": job.status,
            "progress": job.progress,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }
    finally:
        session.close()


@router.get("/jobs")
def list_jobs(status: str | None = None):
    """List all jobs, optionally filtered by status."""
    session = get_session()
    try:
        query = session.query(Job)
        if status:
            query = query.filter_by(status=status)
        jobs = query.order_by(Job.created_at.desc()).all()
        return [
            {
                "id": j.id,
                "video_id": j.video_id,
                "job_type": j.job_type,
                "status": j.status,
                "progress": j.progress,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ]
    finally:
        session.close()


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str):
    """Retry a failed job by creating a new one."""
    session = get_session()
    try:
        old_job = session.query(Job).get(job_id)
        if not old_job:
            raise HTTPException(status_code=404, detail="Job not found")
        if old_job.status != "failed":
            raise HTTPException(status_code=400, detail="Can only retry failed jobs")
        video_id = old_job.video_id
    finally:
        session.close()

    new_job = create_job(video_id, "full_pipeline")
    thread = threading.Thread(
        target=run_full_pipeline, args=(new_job.id, video_id), daemon=True
    )
    thread.start()

    return {"id": new_job.id, "video_id": video_id, "status": "queued", "replaces_job": job_id}
