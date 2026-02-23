"""Card review and listing endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from southview.review.service import get_cards_for_review, get_review_stats, submit_review

router = APIRouter(tags=["cards"])


class ReviewRequest(BaseModel):
    corrected_text: str | None = None
    status: str = "approved"
    reviewed_by: str | None = None


class BatchReviewRequest(BaseModel):
    card_ids: list[str]
    status: str = "approved"
    reviewed_by: str | None = None


@router.get("/cards")
def list_cards(
    video_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 50,
):
    """List cards with OCR results, filterable by video and review status."""
    result = get_cards_for_review(
        video_id=video_id, status=status, page=page, per_page=per_page
    )
    return {
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "pages": result["pages"],
        "cards": [
            {
                "id": card.id,
                "video_id": card.video_id,
                "sequence_index": card.sequence_index,
                "image_path": card.image_path,
                "raw_text": card.ocr_result.raw_text if card.ocr_result else "",
                "corrected_text": card.ocr_result.corrected_text if card.ocr_result else None,
                "confidence_score": card.ocr_result.confidence_score if card.ocr_result else 0.0,
                "review_status": card.ocr_result.review_status if card.ocr_result else "",
            }
            for card in result["cards"]
        ],
    }


@router.get("/cards/{card_id}")
def get_card(card_id: str):
    """Get card detail with OCR result."""
    from southview.db.engine import get_session
    from southview.db.models import Card

    session = get_session()
    try:
        card = session.query(Card).get(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        ocr = card.ocr_result
        return {
            "id": card.id,
            "video_id": card.video_id,
            "sequence_index": card.sequence_index,
            "frame_number": card.frame_number,
            "image_path": card.image_path,
            "image_url": f"/static/frames/{card.video_id}/card_{card.sequence_index:04d}.png",
            "ocr": {
                "raw_text": ocr.raw_text if ocr else "",
                "corrected_text": ocr.corrected_text if ocr else None,
                "confidence_score": ocr.confidence_score if ocr else 0.0,
                "word_confidences": ocr.word_confidences if ocr else "[]",
                "review_status": ocr.review_status if ocr else "",
                "reviewed_by": ocr.reviewed_by if ocr else None,
                "reviewed_at": ocr.reviewed_at.isoformat() if ocr and ocr.reviewed_at else None,
            } if ocr else None,
        }
    finally:
        session.close()


@router.put("/cards/{card_id}/review")
def review_card(card_id: str, body: ReviewRequest):
    """Submit a review for a card."""
    try:
        ocr = submit_review(
            card_id=card_id,
            corrected_text=body.corrected_text,
            status=body.status,
            reviewed_by=body.reviewed_by,
        )
        return {
            "card_id": card_id,
            "review_status": ocr.review_status,
            "reviewed_at": ocr.reviewed_at.isoformat() if ocr.reviewed_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/cards/batch-review")
def batch_review(body: BatchReviewRequest):
    """Batch approve/review multiple cards."""
    results = []
    for card_id in body.card_ids:
        try:
            ocr = submit_review(
                card_id=card_id, status=body.status, reviewed_by=body.reviewed_by
            )
            results.append({"card_id": card_id, "status": "success"})
        except ValueError:
            results.append({"card_id": card_id, "status": "not_found"})
    return {"results": results}


@router.get("/stats")
def stats():
    """Get review workflow statistics."""
    return get_review_stats()
