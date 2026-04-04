"""Job execution orchestrator - runs the full pipeline."""

import logging
import re
from pathlib import Path

from southview.config import get_config
from southview.db.engine import get_session
from southview.db.models import Card, Video
from southview.extraction.frame_extractor import extract_frames
from southview.jobs.cleanup import cleanup_previous_results
from southview.jobs.manager import mark_completed, mark_failed, mark_running, update_progress
from southview.ocr.batch import run_ocr_for_video

logger = logging.getLogger(__name__)


def _source_video_available(video: Video) -> bool:
    return bool(video.filepath and Path(video.filepath).exists())


def _load_existing_cards(session, video_id: str) -> list[Card]:
    return (
        session.query(Card)
        .filter(Card.video_id == video_id)
        .order_by(Card.sequence_index.asc())
        .all()
    )


def _load_frame_results_from_disk(video_id: str) -> list[dict]:
    frames_dir = Path(get_config()["storage"]["frames_dir"]) / video_id
    if not frames_dir.exists():
        return []

    results = []
    for image_path in sorted(frames_dir.glob("card_*.*")):
        match = re.search(r"card_(\d+)", image_path.stem, re.IGNORECASE)
        if not match:
            continue
        seq = int(match.group(1))
        results.append(
            {
                "frame_number": seq,
                "image_path": str(image_path),
                "sequence_index": seq,
            }
        )
    return results


def run_full_pipeline(job_id: str, video_id: str) -> None:
    """Execute the full processing pipeline: frame extraction -> OCR."""
    session = get_session()
    try:
        video = session.query(Video).get(video_id)
        if video is None:
            raise ValueError(f"Video not found: {video_id}")

        mark_running(job_id)
        video.status = "processing"
        session.commit()

        cards: list[Card] = []

        if _source_video_available(video):
            cleanup_previous_results(video_id)

            logger.info("Extracting frames from video %s", video_id)
            frame_results = extract_frames(video.filepath, video_id)
            update_progress(job_id, 50)

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
        else:
            cards = _load_existing_cards(session, video_id)
            if not cards:
                frame_results = _load_frame_results_from_disk(video_id)
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
                if cards:
                    session.commit()

            if not cards:
                raise ValueError(
                    "Original video file is no longer available for reprocessing and no extracted frames remain. "
                    "Please re-upload the video."
                )

            logger.info(
                "Source video missing for %s; reusing %d existing extracted card image(s)",
                video_id,
                len(cards),
            )
            update_progress(job_id, 50)

        logger.info("Running OCR on %d cards", len(cards))
        ocr_result = run_ocr_for_video(video_id, force=True)
        logger.info(
            "OCR complete: %s processed, %s failed",
            ocr_result["processed"],
            ocr_result["failed"],
        )
        update_progress(job_id, 100)

        mark_completed(job_id)
        video.status = "completed"

        delete_source = bool(
            get_config().get("storage", {}).get("delete_source_video_after_processing", False)
        )
        if delete_source and video.filepath:
            video_file = Path(video.filepath)
            if video_file.exists():
                video_file.unlink()
                logger.info("Deleted source video: %s", video.filepath)
            video.filepath = None

        session.commit()
        logger.info("Pipeline complete for video %s: %d cards processed", video_id, len(cards))

    except Exception as e:
        logger.exception("Pipeline failed for video %s", video_id)
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
