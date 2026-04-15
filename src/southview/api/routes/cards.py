from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from southview.config import get_config
from southview.db.engine import get_session
from southview.db.models import Card, STRUCTURED_OCR_FIELDS
from southview.review.service import (
    list_cards as svc_list_cards,
    get_card_detail as svc_get_card_detail,
    ReviewConflictError,
    submit_review as svc_submit_review,
    batch_approve as svc_batch_approve,
)

router = APIRouter(tags=["cards"])

STRUCTURED_FIELDS = list(STRUCTURED_OCR_FIELDS)


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
    id: str = Field(validation_alias="card_id")
    video_id: str
    sequence_index: int
    frame_number: int
    image_path: str
    raw_text: str = ""
    raw_fields_json: str | None = None
    image_url: str | None = None
    review_status: str | None = None
    confidence_score: float | None = None
    rotation_degrees: int | None = 0
    review_version: int | None = 0
    deceased_name: str | None = None
    address: str | None = None
    owner: str | None = None
    relation: str | None = None
    phone: str | None = None
    date_of_death: str | None = None
    date_of_burial: str | None = None
    description: str | None = None
    sex: str | None = None
    age: str | None = None
    grave_type: str | None = None
    grave_fee: str | None = None
    undertaker: str | None = None
    board_of_health_no: str | None = None
    svc_no: str | None = None
    error_message: str | None = None


class CardDetailResponse(BaseModel):
    id: str = Field(validation_alias="card_id")
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
    address: str | None = None
    owner: str | None = None
    relation: str | None = None
    phone: str | None = None
    date_of_death: str | None = None
    date_of_burial: str | None = None
    description: str | None = None
    sex: str | None = None
    age: str | None = None
    grave_type: str | None = None
    grave_fee: str | None = None
    undertaker: str | None = None
    board_of_health_no: str | None = None
    svc_no: str | None = None
    error_message: str | None = None


class ReviewRequest(BaseModel):
    fields: dict[str, Any] | None = None
    status: str  # only 'approved' or 'corrected'
    review_version: int | None = None
    reviewed_by: str | None = None
    # Structured fields (all optional for per-field updates)
    deceased_name: str | None = None
    address: str | None = None
    owner: str | None = None
    relation: str | None = None
    phone: str | None = None
    date_of_death: str | None = None
    date_of_burial: str | None = None
    description: str | None = None
    sex: str | None = None
    age: str | None = None
    grave_type: str | None = None
    grave_fee: str | None = None
    undertaker: str | None = None
    board_of_health_no: str | None = None
    svc_no: str | None = None


class BatchReviewRequest(BaseModel):
    card_ids: list[str]
    reviewed_by: str | None = None


class PaginatedCards(BaseModel):
    cards: list[CardListItem]
    total: int
    page: int
    per_page: int
    pages: int


@router.get("/cards", response_model=PaginatedCards)
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
    per_page: int = Query(50, ge=1, le=500),
):
    result = svc_list_cards(
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
    for r in result["cards"]:
        r["image_url"] = _image_url(r["image_path"])
    return result


@router.get("/cards/{card_id}")
def get_card_detail_endpoint(card_id: str):
    try:
        d = svc_get_card_detail(card_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "id": d["card_id"],
        "video_id": d["video_id"],
        "sequence_index": d["sequence_index"],
        "frame_number": d["frame_number"],
        "image_path": d["image_path"],
        "image_url": _image_url(d["image_path"]),
        "ocr": {
            "raw_text": d.get("raw_text", ""),
            "corrected_text": d.get("corrected_text"),
            "confidence_score": d.get("confidence_score", 0),
            "rotation_degrees": d.get("rotation_degrees", 0),
            "word_confidences": d.get("word_confidences"),
            "review_status": d.get("review_status", "pending"),
            "review_version": d.get("review_version", 0),
            "reviewed_by": d.get("reviewed_by"),
            "reviewed_at": d.get("reviewed_at"),
            "raw_fields_json": d.get("raw_fields_json"),
            "processed_at": d.get("processed_at"),
            "deceased_name": d.get("deceased_name"),
            "address": d.get("address"),
            "owner": d.get("owner"),
            "relation": d.get("relation"),
            "phone": d.get("phone"),
            "date_of_death": d.get("date_of_death"),
            "date_of_burial": d.get("date_of_burial"),
            "description": d.get("description"),
            "sex": d.get("sex"),
            "age": d.get("age"),
            "grave_type": d.get("grave_type"),
            "grave_fee": d.get("grave_fee"),
            "undertaker": d.get("undertaker"),
            "board_of_health_no": d.get("board_of_health_no"),
            "svc_no": d.get("svc_no"),
        },
    }


@router.put("/cards/{card_id}/review")
def submit_review_endpoint(card_id: str, body: ReviewRequest):
    # Collect structured fields that were explicitly set
    structured_fields = {}
    for field in STRUCTURED_FIELDS:
        val = getattr(body, field, None)
        if val is not None:
            structured_fields[field] = val

    try:
        return svc_submit_review(
            card_id,
            fields=body.fields,
            status=body.status,
            review_version=body.review_version,
            reviewed_by=body.reviewed_by,
            structured_fields=structured_fields if structured_fields else None,
        )
    except ReviewConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/cards/batch-review")
def batch_review_endpoint(body: BatchReviewRequest):
    return svc_batch_approve(body.card_ids, reviewed_by=body.reviewed_by)


@router.delete("/cards/{card_id}", status_code=204)
def delete_card_endpoint(card_id: str):
    session = get_session()
    try:
        card = session.query(Card).get(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        image_path = Path(card.image_path) if card.image_path else None
        frames_dir = None
        if image_path:
            try:
                frames_root = Path(get_config()["storage"]["frames_dir"]).resolve()
                frames_dir = image_path.resolve().parent
                frames_dir.relative_to(frames_root)
            except Exception:
                frames_dir = None

        session.delete(card)
        session.commit()

        if image_path and image_path.exists():
            image_path.unlink()

        if frames_dir and frames_dir.exists() and not any(frames_dir.iterdir()):
            frames_dir.rmdir()

        return Response(status_code=204)
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
