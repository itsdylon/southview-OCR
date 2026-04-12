"""Job lifecycle management."""

from datetime import datetime, timezone
import threading

from southview.db.engine import get_session
from southview.db.models import Job

_ACTIVE_JOB_STATUSES = ("queued", "running")
_JOB_CREATION_LOCKS: dict[str, threading.Lock] = {}
_JOB_CREATION_LOCKS_GUARD = threading.Lock()


def _job_creation_lock(video_id: str) -> threading.Lock:
    with _JOB_CREATION_LOCKS_GUARD:
        return _JOB_CREATION_LOCKS.setdefault(video_id, threading.Lock())


def create_job(video_id: str, job_type: str = "full_pipeline") -> tuple[Job, bool]:
    """Create a new job for a video, or return the active one for that video."""
    with _job_creation_lock(video_id):
        session = get_session()
        try:
            existing = (
                session.query(Job)
                .filter(
                    Job.video_id == video_id,
                    Job.status.in_(_ACTIVE_JOB_STATUSES),
                )
                .order_by(Job.created_at.desc())
                .first()
            )
            if existing is not None:
                session.expunge(existing)
                return existing, False

            job = Job(video_id=video_id, job_type=job_type, status="queued")
            session.add(job)
            session.commit()
            session.refresh(job)
            session.expunge(job)
            return job, True
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
