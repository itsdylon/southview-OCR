"""Tests for job lifecycle management."""

from southview.db.engine import get_session
from southview.db.models import Job, Video
from southview.jobs.manager import create_job


def _insert_video(file_hash: str) -> str:
    session = get_session()
    try:
        video = Video(
            filename="test.mp4",
            filepath="/tmp/test.mp4",
            file_hash=file_hash,
            status="uploaded",
        )
        session.add(video)
        session.commit()
        return video.id
    finally:
        session.close()


def test_create_job_reuses_existing_active_job(tmp_db):
    video_id = _insert_video("hash-job-manager-active")

    first_job, created = create_job(video_id, "full_pipeline")
    second_job, created_again = create_job(video_id, "full_pipeline")

    assert created is True
    assert created_again is False
    assert second_job.id == first_job.id

    session = get_session()
    try:
        jobs = session.query(Job).filter_by(video_id=video_id).all()
        assert len(jobs) == 1
    finally:
        session.close()


def test_create_job_creates_new_job_after_previous_job_finishes(tmp_db):
    video_id = _insert_video("hash-job-manager-completed")

    first_job, created = create_job(video_id, "full_pipeline")
    assert created is True

    session = get_session()
    try:
        persisted = session.query(Job).get(first_job.id)
        assert persisted is not None
        persisted.status = "completed"
        session.commit()
    finally:
        session.close()

    second_job, created_again = create_job(video_id, "full_pipeline")

    assert created_again is True
    assert second_job.id != first_job.id


def test_create_job_returns_conflicting_active_job_for_same_video(tmp_db):
    video_id = _insert_video("hash-job-manager-conflict")

    extraction_job, created = create_job(video_id, "extraction")
    assert created is True

    conflicting_job, created_again = create_job(video_id, "full_pipeline")

    assert created_again is False
    assert conflicting_job.id == extraction_job.id
    assert conflicting_job.job_type == "extraction"
