"""API integration tests for video endpoints."""

import json
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
        "SOUTHVIEW_ENV": "development",
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

    def test_upload_strips_path_components_from_filename(self, client, tiny_mp4, monkeypatch, tmp_path):
        """Upload temp writes stay inside the temp directory even with traversal names."""
        upload_tmp = tmp_path / "upload-tmp"
        upload_tmp.mkdir()
        leaked_path = tmp_path / "escape.mp4"

        monkeypatch.setattr("southview.api.routes.videos.tempfile.mkdtemp", lambda: str(upload_tmp))

        with open(tiny_mp4, "rb") as f:
            resp = client.post(
                "/api/videos/upload",
                files={"file": ("../escape.mp4", f, "video/mp4")},
            )

        assert resp.status_code == 200
        assert resp.json()["filename"] == "escape.mp4"
        assert not leaked_path.exists()


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


class TestBlurQueueEndpoint:
    def test_blur_queue_404_when_video_missing(self, client, tmp_config, monkeypatch):
        def fail_if_called():
            raise AssertionError("filesystem config should not be read for unknown videos")

        monkeypatch.setattr("southview.api.routes.videos.get_config", fail_if_called)
        resp = client.get("/api/videos/no-manifest/blur-queue")
        assert resp.status_code == 404

    def test_blur_queue_returns_paginated_items(self, client, tiny_mp4, tmp_config):
        with open(tiny_mp4, "rb") as f:
            upload_resp = client.post(
                "/api/videos/upload",
                files={"file": ("test.mp4", f, "video/mp4")},
            )

        assert upload_resp.status_code == 200
        video_id = upload_resp.json()["id"]
        frames_root = Path(tmp_config["storage"]["frames_dir"])
        video_dir = frames_root / video_id
        video_dir.mkdir(parents=True, exist_ok=True)

        decisions = [
            {"decision": "accepted", "frame_number": 1, "segment_index": 1},
            {
                "decision": "rejected_blur",
                "frame_number": 2,
                "segment_index": 2,
                "sharpness": 12.3,
                "image_path": str(video_dir / "rejected_blur" / "a.jpg"),
                "reason": "below_blur_threshold",
            },
            {
                "decision": "rejected_blur",
                "frame_number": 3,
                "segment_index": 3,
                "sharpness": 8.9,
                "image_path": str(video_dir / "rejected_blur" / "b.jpg"),
                "reason": "below_blur_threshold",
            },
            {"decision": "rejected_dedup", "frame_number": 4, "segment_index": 4},
            {
                "decision": "rejected_blur",
                "frame_number": 5,
                "segment_index": 5,
                "sharpness": 5.1,
                "image_path": str(video_dir / "rejected_blur" / "c.jpg"),
                "reason": "below_blur_threshold",
            },
        ]
        (video_dir / "extraction_decisions.jsonl").write_text(
            "\n".join(json.dumps(row) for row in decisions) + "\n",
            encoding="utf-8",
        )

        manifest = {
            "video_id": video_id,
            "counts": {
                "accepted": 1,
                "rejected_blur": 3,
                "rejected_dedup": 1,
            },
        }
        (video_dir / "extraction_manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )

        with patch("southview.api.routes.videos.get_config", return_value=tmp_config):
            resp = client.get(f"/api/videos/{video_id}/blur-queue?page=1&per_page=2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["video_id"] == video_id
        assert body["total"] == 3
        assert body["page"] == 1
        assert body["per_page"] == 2
        assert body["pages"] == 2
        assert len(body["items"]) == 2
        assert body["items"][0]["frame_number"] == 2
        assert body["items"][1]["frame_number"] == 3
        assert body["counts"]["rejected_blur"] == 3

        with patch("southview.api.routes.videos.get_config", return_value=tmp_config):
            resp2 = client.get(f"/api/videos/{video_id}/blur-queue?page=2&per_page=2")
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert len(body2["items"]) == 1
        assert body2["items"][0]["frame_number"] == 5

    def test_blur_queue_rejects_parent_directory_ids_before_filesystem_access(self, client, monkeypatch):
        def fail_if_called():
            raise AssertionError("filesystem config should not be read for invalid IDs")

        monkeypatch.setattr("southview.api.routes.videos.get_config", fail_if_called)
        resp = client.get("/api/videos/%2e%2e/blur-queue")
        assert resp.status_code == 404
