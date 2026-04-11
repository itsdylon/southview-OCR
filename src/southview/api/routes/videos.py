"""Video upload and listing endpoints."""

import json
import math
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel

from southview.config import get_config
from southview.ingest.video_upload import (
    SUPPORTED_EXTENSIONS,
    get_video as svc_get_video,
    upload_video,
)

router = APIRouter(tags=["videos"])


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
    """Return a basename-only filename safe to use under a temp directory."""
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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/videos/upload", response_model=VideoUploadResponse)
async def upload_video_endpoint(file: UploadFile = File(...)):
    """Upload a video file for processing."""
    suffix = Path(file.filename or "video.mp4").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    tmp_dir = tempfile.mkdtemp()
    original_name = _safe_upload_name(file.filename, suffix)
    tmp_path = Path(tmp_dir) / original_name
    try:
        # Stream the upload in chunks instead of reading entirely into memory
        with open(tmp_path, "wb") as f_out:
            shutil.copyfileobj(file.file, f_out)

        video = upload_video(tmp_path)
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
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


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
                    "sharpness": row.get("sharpness"),
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
