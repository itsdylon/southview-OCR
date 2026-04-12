"""Tests for full-pipeline runner behavior."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from southview.db.engine import get_session
from southview.db.models import Card, Job, Video
from southview.jobs.runner import run_full_pipeline


def test_run_full_pipeline_inserts_cards_in_batches(tmp_path, tmp_db):
    source_video = tmp_path / "source.mp4"
    source_video.write_bytes(b"video-bytes")

    setup_session = get_session()
    try:
        video = Video(
            filename="source.mp4",
            filepath=str(source_video),
            file_hash="hash-runner-test-123",
            status="uploaded",
        )
        setup_session.add(video)
        setup_session.flush()

        job = Job(
            video_id=video.id,
            job_type="full_pipeline",
            status="queued",
            progress=0,
        )
        setup_session.add(job)
        setup_session.commit()
        video_id = video.id
        job_id = job.id
    finally:
        setup_session.close()

    frame_results = [
        {
            "frame_number": idx,
            "image_path": f"/tmp/card_{idx:04d}.jpg",
            "sequence_index": idx,
        }
        for idx in range(1, 1201)
    ]

    runner_session = get_session()
    config = {"frame_extraction": {"db_insert_batch_size": 500}}

    with patch("southview.jobs.runner.get_session", return_value=runner_session), \
         patch("southview.jobs.runner.get_config", return_value=config), \
         patch("southview.jobs.runner.cleanup_previous_results"), \
         patch("southview.jobs.runner.extract_frames", return_value=frame_results), \
         patch("southview.jobs.runner.run_ocr_for_video", return_value={"processed": 1200, "failed": 0}), \
         patch("southview.jobs.runner.mark_running"), \
         patch("southview.jobs.runner.mark_completed"), \
         patch("southview.jobs.runner.update_progress"), \
         patch.object(runner_session, "commit", wraps=runner_session.commit) as commit_spy:
        run_full_pipeline(job_id, video_id)

    # Initial status commit + 3 insert commits + final completion commit = >= 5
    assert commit_spy.call_count >= 5

    verify_session = get_session()
    try:
        cards = (
            verify_session.query(Card)
            .filter_by(video_id=video_id)
            .order_by(Card.sequence_index.asc())
            .all()
        )
        assert len(cards) == 1200
        assert cards[0].sequence_index == 1
        assert cards[-1].sequence_index == 1200
        assert [cards[i].sequence_index for i in (0, 499, 500, 1199)] == [1, 500, 501, 1200]

        video = verify_session.query(Video).get(video_id)
        assert video is not None
        assert video.status == "completed"
        assert video.filepath == str(source_video)
    finally:
        verify_session.close()


def test_run_full_pipeline_fails_fast_when_source_video_missing(tmp_db):
    setup_session = get_session()
    try:
        video = Video(
            filename="missing.mp4",
            filepath=None,
            file_hash="hash-runner-missing-source",
            status="uploaded",
        )
        setup_session.add(video)
        setup_session.flush()

        job = Job(
            video_id=video.id,
            job_type="full_pipeline",
            status="queued",
            progress=0,
        )
        setup_session.add(job)
        setup_session.commit()
        video_id = video.id
        job_id = job.id
    finally:
        setup_session.close()

    with pytest.raises(ValueError, match="source file is unavailable"):
        run_full_pipeline(job_id, video_id)

    verify_session = get_session()
    try:
        job = verify_session.query(Job).get(job_id)
        video = verify_session.query(Video).get(video_id)
        assert job is not None
        assert job.status == "failed"
        assert "Re-upload the video" in (job.error_message or "")
        assert video is not None
        assert video.status == "failed"
    finally:
        verify_session.close()


def test_run_full_pipeline_creates_backup_before_reprocessing(tmp_path, tmp_db):
    source_video = tmp_path / "source.mp4"
    source_video.write_bytes(b"video-bytes")
    frames_root = tmp_path / "frames"
    frames_root.mkdir()

    setup_session = get_session()
    try:
        video = Video(
            filename="source.mp4",
            filepath=str(source_video),
            file_hash="hash-runner-backup-test",
            status="uploaded",
        )
        setup_session.add(video)
        setup_session.flush()

        existing_card = Card(
            video_id=video.id,
            job_id=None,
            frame_number=1,
            image_path=str(frames_root / video.id / "card_0001.jpg"),
            sequence_index=1,
        )
        setup_session.add(existing_card)

        job = Job(
            video_id=video.id,
            job_type="full_pipeline",
            status="queued",
            progress=0,
        )
        setup_session.add(job)
        setup_session.commit()
        video_id = video.id
        job_id = job.id
    finally:
        setup_session.close()

    frame_results = [
        {
            "frame_number": 1,
            "image_path": str(frames_root / video_id / "card_0001.jpg"),
            "sequence_index": 1,
        }
    ]
    config = {
        "storage": {
            "frames_dir": str(frames_root),
            "delete_source_video_after_processing": False,
        },
        "frame_extraction": {"db_insert_batch_size": 500},
        "backup": {"auto_backup_before_jobs": True},
    }

    with patch("southview.jobs.runner.get_config", return_value=config), \
         patch("southview.jobs.runner.create_backup", return_value=str(tmp_path / "backup.db")) as create_backup_mock, \
         patch("southview.jobs.runner.extract_frames", return_value=frame_results), \
         patch("southview.jobs.runner.run_ocr_for_video", return_value={"processed": 1, "failed": 0}), \
         patch("southview.jobs.runner.mark_running"), \
         patch("southview.jobs.runner.mark_completed"), \
         patch("southview.jobs.runner.update_progress"):
        run_full_pipeline(job_id, video_id)

    create_backup_mock.assert_called_once()


def test_run_full_pipeline_restores_previous_frames_when_reprocessing_fails(tmp_path, tmp_db):
    source_video = tmp_path / "source.mp4"
    source_video.write_bytes(b"video-bytes")
    frames_root = tmp_path / "frames"
    original_frames_dir = frames_root / "video-placeholder"
    frames_root.mkdir()

    setup_session = get_session()
    try:
        video = Video(
            filename="source.mp4",
            filepath=str(source_video),
            file_hash="hash-runner-restore-frames",
            status="uploaded",
        )
        setup_session.add(video)
        setup_session.flush()
        original_frames_dir = frames_root / video.id
        original_frames_dir.mkdir(parents=True, exist_ok=True)
        old_frame = original_frames_dir / "old-card.jpg"
        old_frame.write_text("old-frame", encoding="utf-8")

        existing_card = Card(
            video_id=video.id,
            job_id=None,
            frame_number=1,
            image_path=str(old_frame),
            sequence_index=1,
        )
        setup_session.add(existing_card)

        job = Job(
            video_id=video.id,
            job_type="full_pipeline",
            status="queued",
            progress=0,
        )
        setup_session.add(job)
        setup_session.commit()
        video_id = video.id
        job_id = job.id
    finally:
        setup_session.close()

    config = {
        "storage": {
            "frames_dir": str(frames_root),
            "delete_source_video_after_processing": False,
        },
        "frame_extraction": {"db_insert_batch_size": 500},
        "backup": {"auto_backup_before_jobs": True},
    }

    def failing_extract(_video_path, _video_id):
        new_frames_dir = frames_root / video_id
        new_frames_dir.mkdir(parents=True, exist_ok=True)
        (new_frames_dir / "new-card.jpg").write_text("new-frame", encoding="utf-8")
        raise RuntimeError("frame extraction failed")

    with patch("southview.jobs.runner.get_config", return_value=config), \
         patch("southview.jobs.runner.create_backup", return_value=str(tmp_path / "backup.db")), \
         patch("southview.jobs.runner.extract_frames", side_effect=failing_extract), \
         patch("southview.jobs.runner.mark_running"), \
         patch("southview.jobs.runner.mark_failed"):
        with pytest.raises(RuntimeError, match="frame extraction failed"):
            run_full_pipeline(job_id, video_id)

    restored_dir = frames_root / video_id
    assert (restored_dir / "old-card.jpg").exists()
    assert not (restored_dir / "new-card.jpg").exists()
