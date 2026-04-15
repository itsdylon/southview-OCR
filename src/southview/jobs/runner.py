"""Job execution orchestrator — runs the full pipeline."""

import logging
import shutil
import time
from pathlib import Path

from southview.backup.backup_manager import create_backup
from southview.config import get_config
from southview.db.engine import get_session
from southview.db.models import Card, Video
from southview.extraction.frame_extractor import extract_frames
from southview.jobs.cleanup import cleanup_previous_results
from southview.jobs.manager import mark_completed, mark_failed, mark_running, update_progress
from southview.ocr.batch import run_ocr_for_video

logger = logging.getLogger(__name__)


def _frames_dir(video_id: str) -> Path:
    storage = get_config().get("storage", {})
    frames_root = storage.get("frames_dir", "data/frames")
    return Path(frames_root) / video_id


def _stashed_frames_dir(video_id: str, job_id: str) -> Path:
    frames_dir = _frames_dir(video_id)
    return frames_dir.parent / f".{video_id}.pre-reprocess-{job_id}"


def _stash_existing_frames(video_id: str, job_id: str) -> Path | None:
    frames_dir = _frames_dir(video_id)
    if not frames_dir.exists():
        return None
    stashed_dir = _stashed_frames_dir(video_id, job_id)
    if stashed_dir.exists():
        shutil.rmtree(stashed_dir, ignore_errors=True)
    frames_dir.replace(stashed_dir)
    return stashed_dir


def _restore_stashed_frames(video_id: str, stashed_dir: Path | None) -> None:
    if stashed_dir is None or not stashed_dir.exists():
        return
    frames_dir = _frames_dir(video_id)
    if frames_dir.exists():
        shutil.rmtree(frames_dir, ignore_errors=True)
    stashed_dir.replace(frames_dir)


def _discard_stashed_frames(stashed_dir: Path | None) -> None:
    if stashed_dir is not None and stashed_dir.exists():
        shutil.rmtree(stashed_dir, ignore_errors=True)


def _has_previous_results(session, video_id: str) -> bool:
    if session.query(Card.id).filter_by(video_id=video_id).first() is not None:
        return True
    return _frames_dir(video_id).exists()


def _insert_extracted_cards(session, *, video_id: str, job_id: str, frame_results: list[dict]) -> int:
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
    return cards_inserted


def run_extraction_only(job_id: str, video_id: str) -> None:
    """Execute extraction-only processing: frame extraction without OCR."""
    session = get_session()
    extraction_started = time.perf_counter()
    stashed_frames_dir: Path | None = None
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

        had_previous_results = _has_previous_results(session, video_id)
        if had_previous_results and bool(get_config().get("backup", {}).get("auto_backup_before_jobs", True)):
            backup_path = create_backup()
            logger.info("Created pre-reprocessing database backup: %s", backup_path)

        stashed_frames_dir = _stash_existing_frames(video_id, job_id)
        cleanup_previous_results(video_id, remove_frames=False)

        logger.info("Extraction-only start: job_id=%s video_id=%s", job_id, video_id)
        frame_started = time.perf_counter()
        frame_results = extract_frames(source_video_path, video_id)
        frame_elapsed = time.perf_counter() - frame_started
        logger.info(
            "Extraction-only frame selection complete: video_id=%s frames_selected=%d elapsed=%.1fs",
            video_id,
            len(frame_results),
            frame_elapsed,
        )
        _discard_stashed_frames(stashed_frames_dir)
        stashed_frames_dir = None
        update_progress(job_id, 75)

        cards_inserted = _insert_extracted_cards(
            session,
            video_id=video_id,
            job_id=job_id,
            frame_results=frame_results,
        )
        update_progress(job_id, 100)

        mark_completed(job_id)
        video.status = "extracted"
        session.commit()
        logger.info(
            "Extraction-only complete: job_id=%s video_id=%s cards=%d elapsed=%.1fs",
            job_id,
            video_id,
            cards_inserted,
            time.perf_counter() - extraction_started,
        )
    except Exception as e:
        logger.exception(
            "Extraction-only failed: job_id=%s video_id=%s elapsed=%.1fs",
            job_id,
            video_id,
            time.perf_counter() - extraction_started,
        )
        try:
            _restore_stashed_frames(video_id, stashed_frames_dir)
        except Exception:
            logger.exception(
                "Failed to restore stashed frames after extraction-only failure: video_id=%s",
                video_id,
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


def run_full_pipeline(job_id: str, video_id: str) -> None:
    """Execute the full processing pipeline: frame extraction → OCR."""
    session = get_session()
    pipeline_started = time.perf_counter()
    stashed_frames_dir: Path | None = None
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

        had_previous_results = _has_previous_results(session, video_id)
        if had_previous_results and bool(get_config().get("backup", {}).get("auto_backup_before_jobs", True)):
            backup_path = create_backup()
            logger.info("Created pre-reprocessing database backup: %s", backup_path)

        stashed_frames_dir = _stash_existing_frames(video_id, job_id)

        # Idempotency: clean up any previous DB results while preserving old frames until success/failure is known.
        cleanup_previous_results(video_id, remove_frames=False)

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
        _discard_stashed_frames(stashed_frames_dir)
        stashed_frames_dir = None
        update_progress(job_id, 50)

        cards_inserted = _insert_extracted_cards(
            session,
            video_id=video_id,
            job_id=job_id,
            frame_results=frame_results,
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
        ocr_processed = int(ocr_result.get("processed", 0) or 0)
        ocr_failed = int(ocr_result.get("failed", 0) or 0)
        ocr_total = ocr_processed + ocr_failed
        if cards_inserted > 0 and ocr_processed == 0:
            first_error = str(ocr_result.get("first_error") or "unknown OCR error")
            raise RuntimeError(
                f"OCR failed for all {cards_inserted} cards. Example error: {first_error}"
            )
        if ocr_failed > 0:
            raise RuntimeError(
                f"OCR failed for {ocr_failed} card(s) out of {ocr_total}; marking pipeline as failed."
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
        try:
            _restore_stashed_frames(video_id, stashed_frames_dir)
        except Exception:
            logger.exception("Failed to restore stashed frames after pipeline failure: video_id=%s", video_id)
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
