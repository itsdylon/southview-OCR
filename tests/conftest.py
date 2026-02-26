"""Shared test fixtures."""

from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from southview.db.engine import init_db


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    engine = init_db(db_path)
    yield db_path


@pytest.fixture
def tiny_mp4(tmp_path) -> Path:
    """Generate a minimal valid MP4 file (10 frames, 320x240, 30 fps)."""
    video_path = tmp_path / "test_video.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, 30.0, (320, 240))
    for i in range(10):
        frame = np.full((240, 320, 3), fill_value=(i * 25) % 256, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    assert video_path.exists() and video_path.stat().st_size > 0
    return video_path


@pytest.fixture
def tmp_config(tmp_path, tmp_db):
    """Override get_config to use tmp_path for storage directories and tmp_db."""
    config = {
        "database": {"path": str(tmp_db)},
        "storage": {
            "videos_dir": str(tmp_path / "videos"),
            "frames_dir": str(tmp_path / "frames"),
            "backups_dir": str(tmp_path / "backups"),
            "exports_dir": str(tmp_path / "exports"),
        },
    }
    with patch("southview.ingest.video_upload.get_config", return_value=config), \
         patch("southview.config.get_config", return_value=config):
        yield config
