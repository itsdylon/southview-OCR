"""Extraction-only endpoints for frame extraction without OCR."""

import threading

from fastapi import APIRouter, HTTPException

from southview.db.engine import get_session
from southview.db.models import Card, Job, Video
from southview.jobs.manager import create_job
from southview.jobs.runner import run_extraction_only

router = APIRouter(tags=["extraction"])


def _job_response(job: Job) -> dict[str, object]:
    return {
        "id": job.id,
        "video_id": job.video_id,
        "status": job.status,
        "job_type": job.job_type,
    }


@router.post("/extraction/{video_id}/start")
def start_extraction(video_id: str):
    """Start frame extraction only (no OCR) for a video."""
    session = get_session()
    try:
        video = session.query(Video).get(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
    finally:
        session.close()

    job, created = create_job(video_id, "extraction")
    if not created:
        if job.job_type != "extraction":
            raise HTTPException(
                status_code=409,
                detail=f"Video already has an active {job.job_type} job.",
            )
        return _job_response(job)

    thread = threading.Thread(target=run_extraction_only, args=(job.id, video_id), daemon=True)
    thread.start()

    return _job_response(job)


@router.get("/extraction/{job_id}/status")
def get_extraction_status(job_id: str):
    """Get extraction job status and progress."""
    session = get_session()
    try:
        job = session.query(Job).get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.job_type != "extraction":
            raise HTTPException(
                status_code=400, detail="Not an extraction job"
            )
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


@router.get("/extraction/{video_id}/frames")
def list_extracted_frames(video_id: str):
    """List extracted frames for a video (preview before OCR)."""
    session = get_session()
    try:
        cards = (
            session.query(Card)
            .filter_by(video_id=video_id)
            .order_by(Card.sequence_index)
            .all()
        )
        return {
            "video_id": video_id,
            "total": len(cards),
            "frames": [
                {
                    "card_id": card.id,
                    "sequence_index": card.sequence_index,
                    "frame_number": card.frame_number,
                    "image_path": card.image_path,
                    "image_url": f"/static/frames/{card.video_id}/card_{card.sequence_index:04d}.png",
                    "has_ocr": card.ocr_result is not None,
                }
                for card in cards
            ],
        }
    finally:
        session.close()
