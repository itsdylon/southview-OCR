"""Video upload and listing endpoints."""

import json
import logging
import math
import shutil
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel

from southview.config import get_config
from southview.ingest.video_upload import (
    SUPPORTED_EXTENSIONS,
    get_video as svc_get_video,
    upload_video,
)

router = APIRouter(tags=["videos"])
logger = logging.getLogger(__name__)
_DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024 * 1024
_DEFAULT_MAX_CONCURRENT_UPLOADS_PER_CLIENT = 2
_DEFAULT_STAGED_UPLOAD_CLEANUP_AGE_SECONDS = 24 * 60 * 60
_ACTIVE_UPLOADS_BY_CLIENT: dict[str, int] = {}
_UPLOAD_LIMIT_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class VideoUploadResponse(BaseModel):
    id: str
    filename: str
    status: str
    file_hash: str
    file_size_bytes: int | None
    duration_seconds: float | None
    resolution: str | None
    fps: float | None
    frame_count: int | None


class VideoListItem(BaseModel):
    id: str
    filename: str
    status: str
    upload_timestamp: str | None
    duration_seconds: float | None
    file_size_bytes: int | None
    frame_count: int | None
    card_count: int


class VideoDetailResponse(BaseModel):
    id: str
    filename: str
    filepath: str | None
    status: str
    file_hash: str
    upload_timestamp: str | None
    duration_seconds: float | None
    resolution: str | None
    fps: float | None
    frame_count: int | None
    file_size_bytes: int | None
    card_count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolution_str(w: int | None, h: int | None) -> str | None:
    if w and h:
        return f"{w}x{h}"
    return None


def _safe_upload_name(filename: str | None, fallback_suffix: str) -> str:
    """Return a basename-only filename safe to use under storage staging paths."""
    raw_name = (filename or "").replace("\\", "/")
    safe_name = Path(raw_name).name
    if safe_name in {"", ".", ".."}:
        return f"upload{fallback_suffix}"
    return safe_name


def _require_video(video_id: str):
    """Look up a video first so path parameters cannot become filesystem paths."""
    video = svc_get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


def _upload_limits() -> tuple[int, int]:
    config = get_config().get("api", {})
    max_upload_bytes = int(config.get("max_upload_bytes", _DEFAULT_MAX_UPLOAD_BYTES))
    max_concurrent = int(
        config.get(
            "max_concurrent_uploads_per_client",
            _DEFAULT_MAX_CONCURRENT_UPLOADS_PER_CLIENT,
        )
    )
    return max(1, max_upload_bytes), max(1, max_concurrent)


def _videos_dir() -> Path:
    videos_dir = Path(get_config()["storage"]["videos_dir"])
    videos_dir.mkdir(parents=True, exist_ok=True)
    return videos_dir


def _staged_upload_path(suffix: str) -> Path:
    return _videos_dir() / f".upload-{uuid.uuid4().hex}{suffix}"


def _staged_upload_cleanup_age_seconds() -> int:
    config = get_config().get("api", {})
    age_seconds = int(
        config.get(
            "staged_upload_cleanup_age_seconds",
            _DEFAULT_STAGED_UPLOAD_CLEANUP_AGE_SECONDS,
        )
    )
    return max(60, age_seconds)


def cleanup_stale_staged_uploads(*, now: float | None = None) -> int:
    cutoff = (time.time() if now is None else now) - _staged_upload_cleanup_age_seconds()
    removed = 0
    for staged_path in _videos_dir().glob(".upload-*"):
        try:
            if not staged_path.is_file():
                continue
            if staged_path.stat().st_mtime > cutoff:
                continue
            staged_path.unlink(missing_ok=True)
            removed += 1
        except FileNotFoundError:
            continue
        except OSError as exc:
            logger.warning("Could not delete stale staged upload %s: %s", staged_path, exc)
    return removed


def _upload_client_key(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _reserve_upload_slot(client_key: str, max_concurrent: int) -> bool:
    with _UPLOAD_LIMIT_LOCK:
        active = _ACTIVE_UPLOADS_BY_CLIENT.get(client_key, 0)
        if active >= max_concurrent:
            return False
        _ACTIVE_UPLOADS_BY_CLIENT[client_key] = active + 1
    return True


def _release_upload_slot(client_key: str) -> None:
    with _UPLOAD_LIMIT_LOCK:
        active = _ACTIVE_UPLOADS_BY_CLIENT.get(client_key, 0)
        if active <= 1:
            _ACTIVE_UPLOADS_BY_CLIENT.pop(client_key, None)
        else:
            _ACTIVE_UPLOADS_BY_CLIENT[client_key] = active - 1


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/videos/upload", response_model=VideoUploadResponse)
def upload_video_endpoint(request: Request, file: UploadFile = File(...)):
    """Upload a video file for processing."""
    suffix = Path(file.filename or "video.mp4").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    max_upload_bytes, max_concurrent_uploads = _upload_limits()
    client_key = _upload_client_key(request)
    if not _reserve_upload_slot(client_key, max_concurrent_uploads):
        raise HTTPException(
            status_code=429,
            detail="Too many uploads in progress for this client. Try again after one finishes.",
        )

    original_name = _safe_upload_name(file.filename, suffix)
    tmp_path = _staged_upload_path(suffix)
    upload_slot_reserved = True
    try:
        # Stream the upload in chunks instead of reading entirely into memory
        bytes_written = 0
        with open(tmp_path, "wb") as f_out:
            while chunk := file.file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > max_upload_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size is {max_upload_bytes} bytes.",
                    )
                f_out.write(chunk)

        video = upload_video(tmp_path, original_filename=original_name, move_source=True)
        return VideoUploadResponse(
            id=video.id,
            filename=video.filename,
            status=video.status,
            file_hash=video.file_hash,
            file_size_bytes=video.file_size_bytes,
            duration_seconds=video.duration_seconds,
            resolution=_resolution_str(video.resolution_w, video.resolution_h),
            fps=video.fps,
            frame_count=video.frame_count,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OSError:
        raise HTTPException(status_code=500, detail="Server could not store the uploaded file.")
    except Exception:
        raise HTTPException(status_code=500, detail="Server failed to process the uploaded file.")
    finally:
        if upload_slot_reserved:
            _release_upload_slot(client_key)
        file.file.close()
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


@router.get("/videos", response_model=list[VideoListItem])
def list_videos_endpoint(status: str | None = None):
    """List all videos, optionally filtered by status."""
    from southview.db.engine import get_session
    from southview.db.models import Video
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select, func

    session = get_session()
    try:
        stmt = (
            select(Video)
            .options(selectinload(Video.cards))
            .order_by(Video.upload_timestamp.desc())
        )
        if status is not None:
            stmt = stmt.filter_by(status=status)
        videos = list(session.execute(stmt).scalars().all())
        return [
            VideoListItem(
                id=v.id,
                filename=v.filename,
                status=v.status,
                upload_timestamp=v.upload_timestamp.isoformat() if v.upload_timestamp else None,
                duration_seconds=v.duration_seconds,
                file_size_bytes=v.file_size_bytes,
                frame_count=v.frame_count,
                card_count=len(v.cards),
            )
            for v in videos
        ]
    finally:
        session.close()


@router.get("/videos/{video_id}", response_model=VideoDetailResponse)
def get_video_endpoint(video_id: str):
    """Get video details."""
    video = _require_video(video_id)
    return VideoDetailResponse(
        id=video.id,
        filename=video.filename,
        filepath=video.filepath,
        status=video.status,
        file_hash=video.file_hash,
        upload_timestamp=video.upload_timestamp.isoformat() if video.upload_timestamp else None,
        duration_seconds=video.duration_seconds,
        resolution=_resolution_str(video.resolution_w, video.resolution_h),
        fps=video.fps,
        frame_count=video.frame_count,
        file_size_bytes=video.file_size_bytes,
        card_count=len(video.cards),
    )


@router.get("/videos/{video_id}/blur-queue")
def get_blur_queue(
    video_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=1000),
):
    """List blurred frames captured during extraction (list-only queue)."""
    video = _require_video(video_id)
    frames_root = Path(get_config()["storage"]["frames_dir"])
    video_dir = frames_root / video.id
    decisions_path = video_dir / "extraction_decisions.jsonl"
    manifest_path = video_dir / "extraction_manifest.json"

    if not decisions_path.exists() or not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Blur queue not found for video")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        manifest = {}

    start = (page - 1) * per_page
    end = start + per_page
    total = 0
    items = []

    with decisions_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("decision") != "rejected_blur":
                continue
            if start <= total < end:
                items.append({
                    "segment_index": row.get("segment_index"),
                    "frame_number": row.get("frame_number"),
                    "sharpness": row.get("sharpness", row.get("selected_sharpness")),
                    "image_path": row.get("image_path"),
                    "reason": row.get("reason"),
                })
            total += 1

    pages = math.ceil(total / per_page) if total else 0
    return {
        "video_id": video.id,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "counts": manifest.get("counts", {}),
        "items": items,
    }


@router.delete("/videos/{video_id}", status_code=204)
def delete_video_endpoint(video_id: str):
    """Delete a video and all associated jobs/cards/results/files."""
    from southview.db.engine import get_session
    from southview.db.models import Video

    session = get_session()
    try:
        video = session.query(Video).get(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        video_path = Path(video.filepath) if video.filepath else None
        frames_dir = Path(get_config()["storage"]["frames_dir"]) / video_id

        session.delete(video)
        session.commit()

        if video_path and video_path.exists():
            video_path.unlink()

        if frames_dir.exists():
            shutil.rmtree(frames_dir, ignore_errors=True)

        return Response(status_code=204)
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
