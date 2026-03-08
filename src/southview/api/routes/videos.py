"""Video upload and listing endpoints."""

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from southview.ingest.video_upload import (
    SUPPORTED_EXTENSIONS,
    get_video as svc_get_video,
    list_videos as svc_list_videos,
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
    filepath: str
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
    original_name = file.filename or f"upload{suffix}"
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
    video = svc_get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
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
