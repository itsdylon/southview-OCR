"""Video upload and deduplication logic."""

import hashlib
import shutil
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from southview.config import get_config
from southview.db.engine import get_session
from southview.db.models import Video
from southview.ingest.metadata import extract_video_metadata

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm"}


def compute_file_hash(file_path: str | Path, chunk_size: int = 8192) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


def _check_disk_space(dest_dir: Path, file_size: int, margin: float = 1.5) -> None:
    """Raise OSError if there isn't enough free disk space for the file copy.

    Args:
        dest_dir: Directory where the file will be written.
        file_size: Size of the source file in bytes.
        margin: Multiplier for required free space (default 1.5x file size).
    """
    required = int(file_size * margin)
    stat = shutil.disk_usage(dest_dir)
    if stat.free < required:
        raise OSError(
            f"Insufficient disk space: {stat.free} bytes free, "
            f"need {required} bytes ({margin}x file size)"
        )


def _validate_extension(file_path: Path) -> None:
    """Raise ValueError if the file extension is not in SUPPORTED_EXTENSIONS."""
    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )


def _stored_video_path(existing: Video, source_file: Path, dest_dir: Path) -> Path:
    """Compute canonical on-disk path for an existing deduplicated video row."""
    current_path = Path(existing.filepath) if existing.filepath else None
    if current_path and current_path.suffix:
        suffix = current_path.suffix
    else:
        suffix = Path(existing.filename).suffix or source_file.suffix
    return dest_dir / f"{existing.id}{suffix}"


def upload_video(file_path: str | Path) -> Video:
    """
    Ingest a video file: compute hash, check for duplicates, store, and create DB record.

    Returns existing Video if the file was already uploaded (idempotent).
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Video file not found: {file_path}")

    _validate_extension(file_path)

    file_hash = compute_file_hash(file_path)

    session = get_session()
    session.expire_on_commit = False
    try:
        existing = session.execute(
            select(Video).filter_by(file_hash=file_hash)
        ).scalar_one_or_none()
        if existing:
            # Source videos are deleted after successful processing. If a duplicate is
            # uploaded later, restore the file so the same video ID can be reprocessed.
            existing_path = Path(existing.filepath) if existing.filepath else None
            has_existing_source = bool(existing_path and existing_path.exists())
            if not has_existing_source:
                config = get_config()
                dest_dir = Path(config["storage"]["videos_dir"])
                dest_dir.mkdir(parents=True, exist_ok=True)
                _check_disk_space(dest_dir, file_path.stat().st_size)

                restored_path = _stored_video_path(existing, file_path, dest_dir)
                shutil.copy2(file_path, restored_path)
                existing.filepath = str(restored_path)
                session.commit()

            session.expunge(existing)
            return existing

        metadata = extract_video_metadata(file_path)
        file_size = file_path.stat().st_size

        config = get_config()
        dest_dir = Path(config["storage"]["videos_dir"])
        dest_dir.mkdir(parents=True, exist_ok=True)
        _check_disk_space(dest_dir, file_size)

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
            file_size_bytes=file_size,
        )
        session.add(video)
        session.flush()  # get the generated ID

        dest_path = dest_dir / f"{video.id}{file_path.suffix}"
        shutil.copy2(file_path, dest_path)

        video.filepath = str(dest_path)
        session.commit()
        session.expunge(video)
        return video
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_video(video_id: str) -> Video | None:
    """Return a Video by its primary key, or None if not found."""
    session = get_session()
    try:
        video = session.execute(
            select(Video)
            .options(selectinload(Video.cards))
            .filter_by(id=video_id)
        ).scalar_one_or_none()
        if video is not None:
            session.expunge(video)
        return video
    finally:
        session.close()


def list_videos(status: str | None = None) -> list[Video]:
    """Return all videos, optionally filtered by status, newest first."""
    session = get_session()
    try:
        stmt = select(Video).order_by(Video.upload_timestamp.desc())
        if status is not None:
            stmt = stmt.filter_by(status=status)
        videos = list(session.execute(stmt).scalars().all())
        for v in videos:
            session.expunge(v)
        return videos
    finally:
        session.close()
