from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from southview.config import get_config
from southview.review.service import (
    list_cards as svc_list_cards,
    get_card_detail as svc_get_card_detail,
    submit_review as svc_submit_review,
    batch_approve as svc_batch_approve,
)

router = APIRouter(tags=["cards"])


def _image_url(image_path: str) -> str | None:
    # Convert local path under frames_dir to /static/frames/<rel>
    try:
        frames_dir = Path(get_config()["storage"]["frames_dir"]).resolve()
        p = Path(image_path).resolve()
        rel = p.relative_to(frames_dir).as_posix()
        return f"/static/frames/{rel}"
    except Exception:
        return None


class CardListItem(BaseModel):
    card_id: str
    video_id: str
    sequence_index: int
    frame_number: int
    image_path: str
    image_url: str | None = None
    review_status: str | None
    confidence_score: float | None
    deceased_name: str | None = None
    date_of_death: str | None = None
    error_message: str | None = None


class CardDetailResponse(BaseModel):
    card_id: str
    video_id: str
    sequence_index: int
    frame_number: int
    image_path: str
    image_url: str | None = None
    raw_text: str
    raw_fields_json: str | None = None
    confidence_score: float
    review_status: str
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    deceased_name: str | None = None
    date_of_death: str | None = None
    error_message: str | None = None


class ReviewRequest(BaseModel):
    fields: dict[str, Any] | None = None
    status: str  # only 'approved' or 'corrected'
    reviewed_by: str | None = None


class BatchReviewRequest(BaseModel):
    card_ids: list[str]
    reviewed_by: str | None = None


@router.get("/cards", response_model=list[CardListItem])
def list_cards_endpoint(
    video_id: str | None = None,
    # legacy single status filter (optional)
    status: str | None = None,
    # preferred: comma list e.g. approved,corrected
    status_in: str | None = None,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    # search
    q: str | None = None,
    dod_from: str | None = None,
    dod_to: str | None = None,
    sort: str = Query("confidence", pattern="^(confidence|sequence_index)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    rows = svc_list_cards(
        video_id=video_id,
        status=status,
        status_in=status_in,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        q=q,
        dod_from=dod_from,
        dod_to=dod_to,
        sort=sort,
        page=page,
        per_page=per_page,
    )
    for r in rows:
        r["image_url"] = _image_url(r["image_path"])
    return rows


@router.get("/cards/{card_id}", response_model=CardDetailResponse)
def get_card_detail_endpoint(card_id: str):
    try:
        d = svc_get_card_detail(card_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    d["image_url"] = _image_url(d["image_path"])
    return d


@router.put("/cards/{card_id}/review")
def submit_review_endpoint(card_id: str, body: ReviewRequest):
    try:
        return svc_submit_review(
            card_id,
            fields=body.fields,
            status=body.status,
            reviewed_by=body.reviewed_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/cards/batch-review")
def batch_review_endpoint(body: BatchReviewRequest):
    return svc_batch_approve(body.card_ids, reviewed_by=body.reviewed_by)
