"""Video upload and deduplication logic."""

import hashlib
import shutil
from pathlib import Path

from southview.config import get_config
from southview.db.engine import get_session
from southview.db.models import Video
from southview.ingest.metadata import extract_video_metadata


def compute_file_hash(file_path: str | Path, chunk_size: int = 8192) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


def upload_video(file_path: str | Path) -> Video:
    """
    Ingest a video file: compute hash, check for duplicates, store, and create DB record.

    Returns existing Video if the file was already uploaded (idempotent).
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Video file not found: {file_path}")

    file_hash = compute_file_hash(file_path)

    session = get_session()
    try:
        existing = session.query(Video).filter_by(file_hash=file_hash).first()
        if existing:
            return existing

        metadata = extract_video_metadata(file_path)

        video = Video(
            filename=file_path.name,
            filepath="",  # will be set after copy
            file_hash=file_hash,
            status="uploaded",
            duration_seconds=metadata.get("duration_seconds"),
            resolution_w=metadata.get("resolution_w"),
            resolution_h=metadata.get("resolution_h"),
            fps=metadata.get("fps"),
            frame_count=metadata.get("frame_count"),
            file_size_bytes=file_path.stat().st_size,
        )
        session.add(video)
        session.flush()  # get the generated ID

        config = get_config()
        dest_dir = Path(config["storage"]["videos_dir"])
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"{video.id}{file_path.suffix}"
        shutil.copy2(file_path, dest_path)

        video.filepath = str(dest_path)
        session.commit()
        return video
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
