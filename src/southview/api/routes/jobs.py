"""Job management endpoints."""

import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import joinedload

from southview.db.engine import get_session
from southview.db.models import Job, Video
from southview.jobs.manager import create_job
from southview.jobs.runner import run_full_pipeline

router = APIRouter(tags=["jobs"])


def _has_source_video_file(video: Video) -> bool:
    source = (video.filepath or "").strip()
    return bool(source) and Path(source).exists()


def _run_job_safely(job_id: str, video_id: str) -> None:
    try:
        run_full_pipeline(job_id, video_id)
    except Exception:
        # run_full_pipeline already logs and marks the job/video as failed.
        return


@router.post("/jobs/{video_id}/start")
def start_job(video_id: str):
    """Create and start a processing job for a video."""
    session = get_session()
    try:
        video = session.query(Video).get(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        if not _has_source_video_file(video):
            raise HTTPException(
                status_code=409,
                detail="Source video file is unavailable. Re-upload the video before starting a job.",
            )
        video_name = video.filename
    finally:
        session.close()

    job = create_job(video_id, "full_pipeline")

    # Run in background thread (simple single-machine approach)
    thread = threading.Thread(
        target=_run_job_safely, args=(job.id, video_id), daemon=True
    )
    thread.start()

    return {
        "id": job.id,
        "video_id": video_id,
        "video_name": video_name,
        "status": "queued",
        "job_type": "full_pipeline",
        "progress": 0,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    """Get job status and progress."""
    session = get_session()
    try:
        job = session.query(Job).options(joinedload(Job.video)).get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "id": job.id,
            "video_id": job.video_id,
            "video_name": job.video.filename if job.video else None,
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
        query = session.query(Job).options(joinedload(Job.video))
        if status:
            query = query.filter_by(status=status)
        jobs = query.order_by(Job.created_at.desc()).all()
        return [
            {
                "id": j.id,
                "video_id": j.video_id,
                "video_name": j.video.filename if j.video else None,
                "job_type": j.job_type,
                "status": j.status,
                "progress": j.progress,
                "error_message": j.error_message,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
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
        old_job = session.query(Job).options(joinedload(Job.video)).get(job_id)
        if not old_job:
            raise HTTPException(status_code=404, detail="Job not found")
        if old_job.status != "failed":
            raise HTTPException(status_code=400, detail="Can only retry failed jobs")
        if not old_job.video or not _has_source_video_file(old_job.video):
            raise HTTPException(
                status_code=409,
                detail="Source video file is unavailable. Re-upload the video before retrying.",
            )
        video_id = old_job.video_id
        video_name = old_job.video.filename if old_job.video else None
    finally:
        session.close()

    new_job = create_job(video_id, "full_pipeline")
    thread = threading.Thread(
        target=_run_job_safely, args=(new_job.id, video_id), daemon=True
    )
    thread.start()

    return {
        "id": new_job.id,
        "video_id": video_id,
        "video_name": video_name,
        "status": "queued",
        "job_type": "full_pipeline",
        "progress": 0,
        "replaces_job": job_id,
        "created_at": new_job.created_at.isoformat() if new_job.created_at else None,
    }
