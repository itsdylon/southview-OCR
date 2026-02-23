"""Video upload and listing endpoints."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from southview.db.engine import get_session
from southview.db.models import Video
from southview.ingest.video_upload import upload_video

router = APIRouter(tags=["videos"])


@router.post("/videos/upload")
async def upload_video_endpoint(file: UploadFile = File(...)):
    """Upload a video file for processing."""
    with tempfile.NamedTemporaryFile(
        suffix=Path(file.filename or "video.mp4").suffix, delete=False
    ) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        video = upload_video(tmp_path)
        return {
            "id": video.id,
            "filename": video.filename,
            "status": video.status,
            "duration_seconds": video.duration_seconds,
            "resolution": f"{video.resolution_w}x{video.resolution_h}" if video.resolution_w else None,
            "fps": video.fps,
            "frame_count": video.frame_count,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.get("/videos")
def list_videos(status: str | None = None):
    """List all videos, optionally filtered by status."""
    session = get_session()
    try:
        query = session.query(Video)
        if status:
            query = query.filter_by(status=status)
        videos = query.order_by(Video.upload_timestamp.desc()).all()
        return [
            {
                "id": v.id,
                "filename": v.filename,
                "status": v.status,
                "upload_timestamp": v.upload_timestamp.isoformat() if v.upload_timestamp else None,
                "duration_seconds": v.duration_seconds,
            }
            for v in videos
        ]
    finally:
        session.close()


@router.get("/videos/{video_id}")
def get_video(video_id: str):
    """Get video details."""
    session = get_session()
    try:
        video = session.query(Video).get(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        card_count = len(video.cards)
        return {
            "id": video.id,
            "filename": video.filename,
            "filepath": video.filepath,
            "status": video.status,
            "upload_timestamp": video.upload_timestamp.isoformat() if video.upload_timestamp else None,
            "duration_seconds": video.duration_seconds,
            "resolution": f"{video.resolution_w}x{video.resolution_h}" if video.resolution_w else None,
            "fps": video.fps,
            "frame_count": video.frame_count,
            "file_size_bytes": video.file_size_bytes,
            "card_count": card_count,
        }
    finally:
        session.close()
