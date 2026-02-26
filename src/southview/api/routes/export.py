from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from southview.export.service import export_approved_cards_zip

router = APIRouter(tags=["export"])


@router.get("/export/video/{video_id}")
def export_video_approved(
    video_id: str,
    include_corrected: bool = Query(True),
):
    """
    Returns a ZIP of approved/corrected card images for the given video_id.
    """
    try:
        zip_path = export_approved_cards_zip(video_id, include_corrected=include_corrected)
        return FileResponse(
            path=str(zip_path),
            media_type="application/zip",
            filename=zip_path.name,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))