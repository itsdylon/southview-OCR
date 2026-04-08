"""API integration tests for video endpoints."""

import os
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from southview.api.app import create_app
from southview.auth import hash_password


@pytest.fixture
def client(tmp_path, tmp_db, tmp_config):
    """TestClient wired to a temp database and storage directories."""
    config = tmp_config
    auth_env = {
        "SOUTHVIEW_AUTH_USERNAME": "admin",
        "SOUTHVIEW_AUTH_PASSWORD_HASH": hash_password("test-password"),
        "SOUTHVIEW_AUTH_SESSION_SECRET": "test-session-secret",
        "SOUTHVIEW_AUTH_SECURE_COOKIES": "false",
    }
    # Patch the app-level init_db/get_config as well so the startup event
    # doesn't overwrite our temp DB configuration.
    with patch.dict(os.environ, auth_env, clear=False), \
         patch("southview.api.app.init_db"), \
         patch("southview.api.app.get_config", return_value=config):
        app = create_app()
        with TestClient(app) as c:
            login_response = c.post(
                "/api/auth/login",
                json={"username": "admin", "password": "test-password"},
            )
            assert login_response.status_code == 200
            yield c


class TestUploadEndpoint:
    def test_upload_success(self, client, tiny_mp4):
        """POST /api/videos/upload with a valid MP4 returns 200."""
        with open(tiny_mp4, "rb") as f:
            resp = client.post(
                "/api/videos/upload",
                files={"file": ("test.mp4", f, "video/mp4")},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"]
        assert body["filename"] == "test.mp4"
        assert body["status"] == "uploaded"
        assert body["file_hash"]
        assert body["file_size_bytes"] > 0

    def test_upload_duplicate(self, client, tiny_mp4):
        """Uploading the same file twice returns the same video ID."""
        with open(tiny_mp4, "rb") as f:
            first = client.post(
                "/api/videos/upload",
                files={"file": ("test.mp4", f, "video/mp4")},
            ).json()
        with open(tiny_mp4, "rb") as f:
            second = client.post(
                "/api/videos/upload",
                files={"file": ("test.mp4", f, "video/mp4")},
            ).json()
        assert first["id"] == second["id"]

    def test_upload_bad_extension(self, client, tmp_path):
        """POST with an unsupported extension returns 400."""
        bad = tmp_path / "notes.txt"
        bad.write_text("nope")
        with open(bad, "rb") as f:
            resp = client.post(
                "/api/videos/upload",
                files={"file": ("notes.txt", f, "text/plain")},
            )
        assert resp.status_code == 400
        assert "Unsupported file extension" in resp.json()["detail"]


class TestListEndpoint:
    def test_list_empty(self, client):
        """GET /api/videos on an empty DB returns an empty list."""
        resp = client.get("/api/videos")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_upload(self, client, tiny_mp4):
        """GET /api/videos returns the uploaded video."""
        with open(tiny_mp4, "rb") as f:
            client.post(
                "/api/videos/upload",
                files={"file": ("test.mp4", f, "video/mp4")},
            )
        resp = client.get("/api/videos")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["filename"] == "test.mp4"


class TestGetEndpoint:
    def test_get_video(self, client, tiny_mp4):
        """GET /api/videos/{id} returns full detail."""
        with open(tiny_mp4, "rb") as f:
            upload_resp = client.post(
                "/api/videos/upload",
                files={"file": ("test.mp4", f, "video/mp4")},
            ).json()
        vid_id = upload_resp["id"]
        resp = client.get(f"/api/videos/{vid_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == vid_id
        assert body["card_count"] == 0

    def test_get_video_404(self, client):
        """GET /api/videos/{bad_id} returns 404."""
        resp = client.get("/api/videos/nonexistent-uuid")
        assert resp.status_code == 404
