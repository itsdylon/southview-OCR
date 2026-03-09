from __future__ import annotations

from fastapi import APIRouter

from southview.review.service import get_review_stats

router = APIRouter(tags=["stats"])


@router.get("/stats")
def review_stats(video_id: str | None = None):
    """Return flat review counts for the dashboard."""
    data = get_review_stats(video_id=video_id)
    return data["counts"]
