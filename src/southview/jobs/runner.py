"""Job execution orchestrator — runs the full pipeline."""

import logging
import time
from pathlib import Path

from southview.config import get_config
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
    pipeline_started = time.perf_counter()
    try:
        video = session.query(Video).get(video_id)
        if video is None:
            raise ValueError(f"Video not found: {video_id}")

        mark_running(job_id)
        video.status = "processing"
        session.commit()

        source_video_path = (video.filepath or "").strip()
        if not source_video_path:
            raise ValueError(
                "Video source file is unavailable. Re-upload the video before starting or retrying this job."
            )
        if not Path(source_video_path).exists():
            raise FileNotFoundError(
                f"Video source file not found on disk: {source_video_path}. "
                "Re-upload the video before starting or retrying this job."
            )

        # Idempotency: clean up any previous results
        cleanup_previous_results(video_id)

        # Phase 1: Frame extraction (0–50%)
        logger.info("Pipeline start: job_id=%s video_id=%s", job_id, video_id)
        frame_started = time.perf_counter()
        logger.info("Extracting frames: video_id=%s", video_id)
        frame_results = extract_frames(source_video_path, video_id)
        frame_elapsed = time.perf_counter() - frame_started
        logger.info(
            "Frame extraction complete: video_id=%s frames_selected=%d elapsed=%.1fs",
            video_id,
            len(frame_results),
            frame_elapsed,
        )
        update_progress(job_id, 50)

        # Create Card records in chunks for large runs.
        cfg = get_config().get("frame_extraction", {})
        db_insert_batch_size = int(cfg.get("db_insert_batch_size", 500))
        if db_insert_batch_size < 1:
            db_insert_batch_size = 500

        card_insert_started = time.perf_counter()
        cards_inserted = 0
        pending_in_batch = 0
        for result in frame_results:
            card = Card(
                video_id=video_id,
                job_id=job_id,
                frame_number=result["frame_number"],
                image_path=result["image_path"],
                sequence_index=result["sequence_index"],
            )
            session.add(card)
            cards_inserted += 1
            pending_in_batch += 1
            if pending_in_batch >= db_insert_batch_size:
                session.commit()
                pending_in_batch = 0
        if pending_in_batch:
            session.commit()
        card_insert_elapsed = time.perf_counter() - card_insert_started
        logger.info(
            "Card insert complete: video_id=%s cards=%d elapsed=%.1fs batch_size=%d",
            video_id,
            cards_inserted,
            card_insert_elapsed,
            db_insert_batch_size,
        )

        # Phase 2: OCR (50–100%)
        ocr_started = time.perf_counter()
        logger.info("Running OCR: video_id=%s cards=%d", video_id, cards_inserted)
        ocr_result = run_ocr_for_video(video_id, force=True)
        ocr_elapsed = time.perf_counter() - ocr_started
        logger.info(
            (
                "OCR stage complete: video_id=%s processed=%d failed=%d "
                "elapsed=%.1fs"
            ),
            video_id,
            ocr_result["processed"],
            ocr_result["failed"],
            ocr_elapsed,
        )
        if cards_inserted > 0 and int(ocr_result.get("processed", 0)) == 0:
            first_error = str(ocr_result.get("first_error") or "unknown OCR error")
            raise RuntimeError(
                f"OCR failed for all {cards_inserted} cards. Example error: {first_error}"
            )
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
        pipeline_elapsed = time.perf_counter() - pipeline_started
        logger.info(
            (
                "Pipeline complete: job_id=%s video_id=%s cards=%d "
                "elapsed=%.1fs"
            ),
            job_id,
            video_id,
            cards_inserted,
            pipeline_elapsed,
        )

    except Exception as e:
        pipeline_elapsed = time.perf_counter() - pipeline_started
        logger.exception(
            "Pipeline failed: job_id=%s video_id=%s elapsed=%.1fs",
            job_id,
            video_id,
            pipeline_elapsed,
        )
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
