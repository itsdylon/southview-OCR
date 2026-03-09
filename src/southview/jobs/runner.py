"""Job execution orchestrator — runs the full pipeline."""

import logging
from pathlib import Path

from southview.db.engine import get_session
from southview.db.models import Card, Video
from southview.extraction.frame_extractor import extract_frames
from southview.jobs.cleanup import cleanup_previous_results
from southview.jobs.manager import mark_completed, mark_failed, mark_running, update_progress
from southview.ocr.batch import run_ocr_for_video

logger = logging.getLogger(__name__)


def run_full_pipeline(job_id: str, video_id: str) -> None:
    """Execute the full processing pipeline: frame extraction → OCR."""
    session = get_session()
    try:
        video = session.query(Video).get(video_id)
        if video is None:
            raise ValueError(f"Video not found: {video_id}")

        mark_running(job_id)
        video.status = "processing"
        session.commit()

        # Idempotency: clean up any previous results
        cleanup_previous_results(video_id)

        # Phase 1: Frame extraction (0–50%)
        logger.info(f"Extracting frames from video {video_id}")
        frame_results = extract_frames(video.filepath, video_id)
        update_progress(job_id, 50)

        # Create Card records
        cards = []
        for result in frame_results:
            card = Card(
                video_id=video_id,
                job_id=job_id,
                frame_number=result["frame_number"],
                image_path=result["image_path"],
                sequence_index=result["sequence_index"],
            )
            session.add(card)
            cards.append(card)
        session.commit()

        # Phase 2: OCR (50–100%)
        logger.info(f"Running OCR on {len(cards)} cards")
        ocr_result = run_ocr_for_video(video_id, force=True)
        logger.info(f"OCR complete: {ocr_result['processed']} processed, {ocr_result['failed']} failed")
        update_progress(job_id, 100)

        mark_completed(job_id)
        video.status = "completed"

        # Delete source video file — only extracted frames are kept
        if video.filepath:
            video_file = Path(video.filepath)
            if video_file.exists():
                video_file.unlink()
                logger.info(f"Deleted source video: {video.filepath}")
            video.filepath = None

        session.commit()
        logger.info(f"Pipeline complete for video {video_id}: {len(cards)} cards processed")

    except Exception as e:
        logger.exception(f"Pipeline failed for video {video_id}")
        mark_failed(job_id, str(e))
        try:
            video = session.query(Video).get(video_id)
            if video:
                video.status = "failed"
                session.commit()
        except Exception:
            session.rollback()
        raise
    finally:
        session.close()
