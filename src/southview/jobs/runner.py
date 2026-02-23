"""Job execution orchestrator — runs the full pipeline."""

import logging

from southview.db.engine import get_session
from southview.db.models import Card, Video
from southview.extraction.frame_extractor import extract_frames
from southview.jobs.cleanup import cleanup_previous_results
from southview.jobs.manager import mark_completed, mark_failed, mark_running, update_progress
from southview.ocr.processor import process_card

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
        for i, card in enumerate(cards):
            try:
                process_card(card)
            except Exception as e:
                logger.error(f"OCR failed for card {card.id}: {e}")
                # Continue processing remaining cards

            progress = 50 + int((i + 1) / max(len(cards), 1) * 50)
            update_progress(job_id, progress)

        mark_completed(job_id)
        video.status = "completed"
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
