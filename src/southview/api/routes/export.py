from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

from southview.export.exporter import export_csv, export_json
from southview.export.service import export_approved_cards_zip

router = APIRouter(tags=["export"])


@router.get("/export")
def export_data(
    format: str = Query("csv", pattern="^(csv|json)$"),
    video_id: str | None = Query(None),
    status: str | None = Query(None),
):
    """Export card data as CSV or JSON."""
    if format == "json":
        data = export_json(video_id=video_id, status=status)
        return Response(content=data, media_type="application/json")
    else:
        data = export_csv(video_id=video_id, status=status)
        return Response(content=data, media_type="text/csv")


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
