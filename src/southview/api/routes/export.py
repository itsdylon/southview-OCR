"""Data export endpoints."""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, JSONResponse

from southview.export.exporter import export_csv, export_json

router = APIRouter(tags=["export"])


@router.get("/export")
def export_data(
    format: str = "json",
    video_id: str | None = None,
    status: str | None = None,
):
    """Export card data as CSV or JSON."""
    if format == "csv":
        csv_str = export_csv(video_id=video_id, status=status)
        return PlainTextResponse(
            content=csv_str,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=export.csv"},
        )
    else:
        json_str = export_json(video_id=video_id, status=status)
        return JSONResponse(
            content={"data": json_str},
            headers={"Content-Disposition": "attachment; filename=export.json"},
        )
