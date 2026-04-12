"""API tests for job start deduplication."""

import os
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from southview.api.app import create_app
from southview.auth import hash_password
from southview.db.engine import get_session
from southview.db.models import Video


class _DummyThread:
    starts = 0

    def __init__(self, target=None, args=(), daemon=None):
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self):
        type(self).starts += 1


@pytest.fixture
def client(tmp_config):
    auth_env = {
        "SOUTHVIEW_ENV": "development",
        "SOUTHVIEW_AUTH_USERNAME": "admin",
        "SOUTHVIEW_AUTH_PASSWORD_HASH": hash_password("test-password"),
        "SOUTHVIEW_AUTH_SESSION_SECRET": "test-session-secret",
        "SOUTHVIEW_AUTH_SECURE_COOKIES": "false",
    }
    with patch.dict(os.environ, auth_env, clear=False), \
         patch("southview.api.app.init_db"), \
         patch("southview.api.app.get_config", return_value=tmp_config):
        app = create_app()
        with TestClient(app) as client:
            login_response = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "test-password"},
            )
            assert login_response.status_code == 200
            yield client


def test_start_job_reuses_existing_active_job(client, tmp_path, monkeypatch):
    source_video = tmp_path / "source.mp4"
    source_video.write_bytes(b"video-bytes")

    session = get_session()
    try:
        video = Video(
            filename="source.mp4",
            filepath=str(source_video),
            file_hash="hash-jobs-api-active",
            status="uploaded",
        )
        session.add(video)
        session.commit()
        video_id = video.id
    finally:
        session.close()

    monkeypatch.setattr("southview.api.routes.jobs.threading.Thread", _DummyThread)
    _DummyThread.starts = 0

    first = client.post(f"/api/jobs/{video_id}/start")
    second = client.post(f"/api/jobs/{video_id}/start")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert _DummyThread.starts == 1


def test_start_job_rejects_when_different_job_type_is_active(client, tmp_path, monkeypatch):
    source_video = tmp_path / "source.mp4"
    source_video.write_bytes(b"video-bytes")

    session = get_session()
    try:
        video = Video(
            filename="source.mp4",
            filepath=str(source_video),
            file_hash="hash-jobs-api-conflict",
            status="uploaded",
        )
        session.add(video)
        session.commit()
        video_id = video.id
    finally:
        session.close()

    monkeypatch.setattr(
        "southview.api.routes.jobs.create_job",
        lambda _video_id, _job_type: (
            type("ExistingJob", (), {
                "id": "existing-job",
                "video_id": video_id,
                "status": "running",
                "job_type": "extraction",
                "progress": 40,
                "created_at": None,
            })(),
            False,
        ),
    )

    response = client.post(f"/api/jobs/{video_id}/start")

    assert response.status_code == 409
    assert "active extraction job" in response.json()["detail"]
