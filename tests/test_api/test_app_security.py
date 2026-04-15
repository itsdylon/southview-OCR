"""Security-focused tests for the FastAPI app shell."""

import os
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from southview.api.app import create_app


def _test_config(tmp_path: Path) -> dict[str, dict[str, str]]:
    return {
        "database": {"path": str(tmp_path / "test.db")},
        "storage": {
            "videos_dir": str(tmp_path / "videos"),
            "frames_dir": str(tmp_path / "frames"),
            "backups_dir": str(tmp_path / "backups"),
            "exports_dir": str(tmp_path / "exports"),
        },
    }


def test_spa_fallback_serves_frontend_files_only(tmp_path):
    frontend_dir = tmp_path / "frontend-dist"
    assets_dir = frontend_dir / "assets"
    frontend_dir.mkdir()
    assets_dir.mkdir()
    (frontend_dir / "index.html").write_text("INDEX", encoding="utf-8")
    (frontend_dir / "hello.txt").write_text("HELLO", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("TOP SECRET", encoding="utf-8")

    with patch("southview.api.app.init_db"), \
         patch("southview.api.app.get_config", return_value=_test_config(tmp_path)), \
         patch("southview.api.app._FRONTEND_DIR", frontend_dir):
        app = create_app()
        with TestClient(app) as client:
            file_response = client.get("/hello.txt")
            assert file_response.status_code == 200
            assert file_response.text == "HELLO"

            traversal_response = client.get("/%2e%2e/secret.txt")
            assert traversal_response.status_code == 200
            assert traversal_response.text == "INDEX"


def test_cors_uses_configured_origins_and_explicit_methods(tmp_path):
    frontend_dir = tmp_path / "frontend-dist"
    assets_dir = frontend_dir / "assets"
    frontend_dir.mkdir()
    assets_dir.mkdir()
    (frontend_dir / "index.html").write_text("INDEX", encoding="utf-8")

    with patch("southview.api.app.init_db"), \
         patch("southview.api.app.get_config", return_value=_test_config(tmp_path)), \
         patch("southview.api.app._FRONTEND_DIR", frontend_dir), \
         patch.dict(os.environ, {"SOUTHVIEW_CORS_ORIGINS": "https://southview.example"}, clear=False):
        app = create_app()
        with TestClient(app) as client:
            response = client.options(
                "/api/videos",
                headers={
                    "Origin": "https://southview.example",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type",
                },
            )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://southview.example"
    assert response.headers["access-control-allow-methods"] == "GET, POST, PUT, DELETE"
    assert response.headers["access-control-allow-headers"] == "Accept, Accept-Language, Content-Language, Content-Type"


def test_startup_cleans_stale_staged_uploads(tmp_path):
    config = _test_config(tmp_path)
    videos_dir = Path(config["storage"]["videos_dir"])
    videos_dir.mkdir(parents=True, exist_ok=True)
    stale_upload = videos_dir / ".upload-stale.mp4"
    real_video = videos_dir / "real-video.mp4"
    stale_upload.write_text("stale", encoding="utf-8")
    real_video.write_text("real", encoding="utf-8")

    now = 1_000_000.0
    os.utime(stale_upload, (now - 120, now - 120))

    with patch("southview.api.app.init_db"), \
         patch("southview.api.app.get_config", return_value=config), \
         patch(
             "southview.api.routes.videos.get_config",
             return_value={
                 **config,
                 "api": {"staged_upload_cleanup_age_seconds": 60},
             },
         ), \
         patch("southview.api.routes.videos.time.time", return_value=now), \
         patch("southview.api.app._FRONTEND_DIR", tmp_path / "missing-frontend"):
        app = create_app()
        with TestClient(app):
            pass

    assert not stale_upload.exists()
    assert real_video.exists()
