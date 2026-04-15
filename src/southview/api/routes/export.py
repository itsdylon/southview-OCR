from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

from southview.export.exporter import export_csv, export_json, has_export_rows
from southview.export.service import ExportIncompleteError, export_approved_cards_zip

router = APIRouter(tags=["export"])


@router.get("/export")
def export_data(
    format: str = Query("csv", pattern="^(csv|json)$"),
    video_id: str | None = Query(None),
    status: str | None = Query(None),
):
    """Export card data as CSV or JSON."""
    if not has_export_rows(video_id=video_id, status=status):
        raise HTTPException(status_code=404, detail="No exportable records found for the selected filters.")

    media_type = "application/json" if format == "json" else "text/csv; charset=utf-8"
    suffix = "json" if format == "json" else "csv"
    if format == "json":
        data = export_json(video_id=video_id, status=status)
    else:
        data = export_csv(video_id=video_id, status=status)

    headers = {
        "Content-Disposition": f'attachment; filename="southview_export.{suffix}"',
    }
    return Response(content=data, media_type=media_type, headers=headers)


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
        if isinstance(e, ExportIncompleteError):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))
