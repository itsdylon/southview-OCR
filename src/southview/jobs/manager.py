"""Job lifecycle management."""

from datetime import datetime, timezone

from southview.db.engine import get_session
from southview.db.models import Job


def create_job(video_id: str, job_type: str = "full_pipeline") -> Job:
    """Create a new job for a video."""
    session = get_session()
    try:
        job = Job(video_id=video_id, job_type=job_type, status="queued")
        session.add(job)
        session.commit()
        session.refresh(job)
        return job
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def mark_running(job_id: str) -> None:
    """Mark a job as running."""
    session = get_session()
    try:
        job = session.query(Job).get(job_id)
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def update_progress(job_id: str, progress: int) -> None:
    """Update job progress (0–100)."""
    session = get_session()
    try:
        job = session.query(Job).get(job_id)
        job.progress = min(max(progress, 0), 100)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def mark_completed(job_id: str) -> None:
    """Mark a job as completed."""
    session = get_session()
    try:
        job = session.query(Job).get(job_id)
        job.status = "completed"
        job.progress = 100
        job.completed_at = datetime.now(timezone.utc)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def mark_failed(job_id: str, error_message: str) -> None:
    """Mark a job as failed with an error message."""
    session = get_session()
    try:
        job = session.query(Job).get(job_id)
        job.status = "failed"
        job.error_message = error_message
        job.completed_at = datetime.now(timezone.utc)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
