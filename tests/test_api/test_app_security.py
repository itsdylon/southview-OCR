"""Security-focused tests for the FastAPI app shell."""

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
