"""Tests for video upload and deduplication."""

import hashlib
from pathlib import Path

import pytest

from southview.db.engine import init_db, get_session
from southview.db.models import Video
from southview.ingest.video_upload import (
    SUPPORTED_EXTENSIONS,
    compute_file_hash,
    get_video,
    list_videos,
    upload_video,
)


# ---------------------------------------------------------------------------
# compute_file_hash
# ---------------------------------------------------------------------------

class TestComputeFileHash:
    def test_deterministic_hash(self, tmp_path):
        """Hash of known content matches expected SHA-256."""
        p = tmp_path / "hello.bin"
        p.write_bytes(b"hello world")
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert compute_file_hash(p) == expected

    def test_large_file_chunked(self, tmp_path):
        """Chunked reading produces the same hash as a single read."""
        data = b"x" * 100_000
        p = tmp_path / "large.bin"
        p.write_bytes(data)
        expected = hashlib.sha256(data).hexdigest()
        # Use a small chunk size to force multiple iterations
        assert compute_file_hash(p, chunk_size=1024) == expected


# ---------------------------------------------------------------------------
# upload_video
# ---------------------------------------------------------------------------

class TestUploadVideo:
    def test_upload_new_video(self, tmp_db, tmp_config, tiny_mp4):
        """Happy path: new video is stored and a Video record is created."""
        video = upload_video(tiny_mp4)
        assert video.id is not None
        assert video.filename == tiny_mp4.name
        assert video.status == "uploaded"
        assert video.file_hash == compute_file_hash(tiny_mp4)
        assert video.file_size_bytes > 0
        assert video.duration_seconds is not None
        # The stored file should actually exist
        assert Path(video.filepath).exists()

    def test_upload_duplicate_returns_existing(self, tmp_db, tmp_config, tiny_mp4):
        """Uploading the same file twice returns the original Video (idempotent)."""
        first = upload_video(tiny_mp4)
        second = upload_video(tiny_mp4)
        assert first.id == second.id

    def test_upload_duplicate_restores_missing_source_file(self, tmp_db, tmp_config, tiny_mp4):
        """If a deduped video's source file was cleaned up, duplicate upload restores it."""
        first = upload_video(tiny_mp4)
        original_path = Path(first.filepath)
        assert original_path.exists()

        session = get_session()
        try:
            video = session.query(Video).get(first.id)
            video.filepath = None
            video.status = "completed"
            session.commit()
        finally:
            session.close()

        original_path.unlink()
        assert not original_path.exists()

        second = upload_video(tiny_mp4)
        assert second.id == first.id
        assert second.filepath
        assert Path(second.filepath).exists()

    def test_upload_nonexistent_file_raises(self, tmp_db, tmp_config):
        """FileNotFoundError when the source path doesn't exist."""
        with pytest.raises(FileNotFoundError):
            upload_video(Path("/nonexistent/video.mp4"))

    def test_upload_invalid_extension_raises(self, tmp_db, tmp_config, tmp_path):
        """Unsupported extension is rejected before any heavy work."""
        bad = tmp_path / "notes.txt"
        bad.write_text("not a video")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            upload_video(bad)

    def test_upload_corrupt_video_raises(self, tmp_db, tmp_config, tmp_path):
        """A file with the right extension but invalid content is rejected."""
        bad = tmp_path / "corrupt.mp4"
        bad.write_bytes(b"this is not a video file at all")
        with pytest.raises(ValueError, match="Could not open video"):
            upload_video(bad)

    def test_upload_move_source_renames_staged_file_into_storage(self, tmp_db, tmp_config, tiny_mp4, tmp_path):
        staged = tmp_path / ".upload-stage.mp4"
        staged.write_bytes(tiny_mp4.read_bytes())

        video = upload_video(staged, original_filename="original.mp4", move_source=True)

        assert video.filename == "original.mp4"
        assert Path(video.filepath).exists()
        assert not staged.exists()


# ---------------------------------------------------------------------------
# get_video / list_videos
# ---------------------------------------------------------------------------

class TestServiceLayer:
    def test_get_video_found(self, tmp_db, tmp_config, tiny_mp4):
        """get_video returns the Video when it exists."""
        created = upload_video(tiny_mp4)
        found = get_video(created.id)
        assert found is not None
        assert found.id == created.id

    def test_get_video_not_found(self, tmp_db, tmp_config):
        """get_video returns None for a non-existent ID."""
        assert get_video("nonexistent-uuid") is None

    def test_list_videos_empty(self, tmp_db, tmp_config):
        """Empty database returns an empty list."""
        assert list_videos() == []

    def test_list_videos_with_filter(self, tmp_db, tmp_config, tiny_mp4):
        """Status filter returns only matching videos."""
        upload_video(tiny_mp4)
        assert len(list_videos(status="uploaded")) == 1
        assert len(list_videos(status="processed")) == 0
