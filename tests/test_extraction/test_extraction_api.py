"""API integration tests for extraction-only endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from southview.api.app import create_app
from southview.db.engine import get_session
from southview.db.models import Card, Job, Video
from southview.jobs.manager import create_job


@pytest.fixture
def client(tmp_path, tmp_db, tmp_config):
    """TestClient wired to a temp database and storage directories."""
    config = tmp_config
    with patch("southview.api.app.init_db"), \
         patch("southview.api.app.get_config", return_value=config):
        app = create_app()
        with TestClient(app) as c:
            yield c


def _upload_video(client, tiny_mp4):
    """Helper: upload a video and return response body."""
    with open(tiny_mp4, "rb") as f:
        resp = client.post(
            "/api/videos/upload",
            files={"file": ("test.mp4", f, "video/mp4")},
        )
    assert resp.status_code == 200
    return resp.json()


class TestStartExtraction:
    def test_returns_queued(self, client, tiny_mp4):
        upload = _upload_video(client, tiny_mp4)
        with patch("southview.api.routes.extraction.run_extraction_only"):
            resp = client.post(f"/api/extraction/{upload['id']}/start")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "queued"
        assert body["job_type"] == "extraction"
        assert body["video_id"] == upload["id"]
        assert body["id"]  # job ID exists

    def test_video_not_found(self, client):
        resp = client.post("/api/extraction/nonexistent-uuid/start")
        assert resp.status_code == 404

    def test_job_type_is_extraction(self, client, tiny_mp4):
        upload = _upload_video(client, tiny_mp4)
        with patch("southview.api.routes.extraction.run_extraction_only"):
            resp = client.post(f"/api/extraction/{upload['id']}/start")
        body = resp.json()
        # Verify in DB too
        session = get_session()
        try:
            job = session.query(Job).get(body["id"])
            assert job.job_type == "extraction"
        finally:
            session.close()


class TestExtractionStatus:
    def test_returns_job_info(self, client, tiny_mp4):
        upload = _upload_video(client, tiny_mp4)
        with patch("southview.api.routes.extraction.run_extraction_only"):
            start = client.post(f"/api/extraction/{upload['id']}/start").json()
        resp = client.get(f"/api/extraction/{start['id']}/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == start["id"]
        assert body["job_type"] == "extraction"
        assert body["progress"] is not None
        assert "status" in body

    def test_job_not_found(self, client):
        resp = client.get("/api/extraction/nonexistent-uuid/status")
        assert resp.status_code == 404

    def test_wrong_job_type(self, client, tiny_mp4):
        """Requesting status on a full_pipeline job returns 400."""
        upload = _upload_video(client, tiny_mp4)
        with patch("southview.api.routes.jobs.run_full_pipeline"):
            start = client.post(f"/api/jobs/{upload['id']}/start").json()
        resp = client.get(f"/api/extraction/{start['id']}/status")
        assert resp.status_code == 400
        assert "Not an extraction job" in resp.json()["detail"]

    def test_full_pipeline_start_requires_source_video_file(self, client, tmp_db):
        session = get_session()
        try:
            video = Video(
                filename="missing.mp4",
                filepath=None,
                file_hash="missing-source-hash",
                status="completed",
            )
            session.add(video)
            session.commit()
            vid = video.id
        finally:
            session.close()

        resp = client.post(f"/api/jobs/{vid}/start")
        assert resp.status_code == 409
        assert "Source video file is unavailable" in resp.json()["detail"]


class TestListFrames:
    def test_empty_before_extraction(self, client):
        resp = client.get("/api/extraction/some-video-id/frames")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["frames"] == []

    def test_returns_cards_after_extraction(self, client, tmp_db):
        """Insert Card records directly and verify frames endpoint returns them."""
        session = get_session()
        try:
            video = Video(
                filename="test.mp4",
                filepath="/fake/path.mp4",
                file_hash="abc123test",
                status="extracted",
            )
            session.add(video)
            session.flush()

            job = Job(
                video_id=video.id,
                job_type="extraction",
                status="completed",
            )
            session.add(job)
            session.flush()

            card = Card(
                video_id=video.id,
                job_id=job.id,
                frame_number=10,
                image_path="/fake/card_0001.png",
                sequence_index=1,
            )
            session.add(card)
            session.commit()
            vid = video.id
        finally:
            session.close()

        resp = client.get(f"/api/extraction/{vid}/frames")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["video_id"] == vid
        frame = body["frames"][0]
        assert frame["sequence_index"] == 1
        assert frame["frame_number"] == 10
        assert frame["has_ocr"] is False
        assert "/static/frames/" in frame["image_url"]

    def test_multiple_cards_ordered(self, client, tmp_db):
        """Multiple cards are returned ordered by sequence_index."""
        session = get_session()
        try:
            video = Video(
                filename="test.mp4",
                filepath="/fake/path.mp4",
                file_hash="xyz789test",
                status="extracted",
            )
            session.add(video)
            session.flush()

            job = Job(
                video_id=video.id,
                job_type="extraction",
                status="completed",
            )
            session.add(job)
            session.flush()

            for i in [3, 1, 2]:  # Insert out of order
                card = Card(
                    video_id=video.id,
                    job_id=job.id,
                    frame_number=i * 10,
                    image_path=f"/fake/card_{i:04d}.png",
                    sequence_index=i,
                )
                session.add(card)
            session.commit()
            vid = video.id
        finally:
            session.close()

        resp = client.get(f"/api/extraction/{vid}/frames")
        body = resp.json()
        assert body["total"] == 3
        indices = [f["sequence_index"] for f in body["frames"]]
        assert indices == [1, 2, 3]
