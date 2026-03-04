from __future__ import annotations

from fastapi import APIRouter

from southview.review.service import get_review_stats

router = APIRouter(tags=["stats"])


@router.get("/stats/review")
def review_stats(video_id: str | None = None):
    return get_review_stats(video_id=video_id)
