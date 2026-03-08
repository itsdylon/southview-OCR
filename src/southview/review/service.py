"""Review business logic — approve, correct, and query cards."""

from datetime import datetime, timezone

from sqlalchemy.orm import joinedload

from southview.db.engine import get_session
from southview.db.models import Card, OCRResult

ALLOWED_STRUCTURED_FIELDS = {
    "deceased_name", "address", "owner", "relation", "phone",
    "date_of_death", "date_of_burial", "description", "sex", "age",
    "grave_type", "grave_fee", "undertaker", "board_of_health_no", "svc_no",
}


def get_cards_for_review(
    video_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    """Fetch paginated cards with OCR results for review."""
    session = get_session()
    try:
        query = session.query(Card).options(joinedload(Card.ocr_result))

        if video_id:
            query = query.filter(Card.video_id == video_id)
        if status:
            query = query.join(OCRResult).filter(OCRResult.review_status == status)

        total = query.count()
        cards = (
            query.order_by(Card.video_id, Card.sequence_index)
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return {
            "cards": cards,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        }
    finally:
        session.close()


def submit_review(
    card_id: str,
    corrected_text: str | None = None,
    status: str = "approved",
    reviewed_by: str | None = None,
    structured_fields: dict | None = None,
) -> OCRResult:
    """Submit a review for a card (approve or correct)."""
    session = get_session()
    try:
        ocr = session.query(OCRResult).filter_by(card_id=card_id).first()
        if ocr is None:
            raise ValueError(f"No OCR result found for card {card_id}")

        if corrected_text is not None:
            ocr.corrected_text = corrected_text
            ocr.review_status = "corrected"
        else:
            ocr.review_status = status

        ocr.reviewed_by = reviewed_by
        ocr.reviewed_at = datetime.now(timezone.utc)

        # Apply structured field updates
        if structured_fields:
            for key, value in structured_fields.items():
                if key in ALLOWED_STRUCTURED_FIELDS:
                    setattr(ocr, key, value)

        session.commit()
        session.refresh(ocr)
        return ocr
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_review_stats() -> dict:
    """Get summary statistics for the review workflow."""
    session = get_session()
    try:
        total = session.query(OCRResult).count()
        pending = session.query(OCRResult).filter_by(review_status="pending").count()
        flagged = session.query(OCRResult).filter_by(review_status="flagged").count()
        approved = session.query(OCRResult).filter_by(review_status="approved").count()
        corrected = session.query(OCRResult).filter_by(review_status="corrected").count()

        from sqlalchemy import func
        avg_conf = session.query(func.avg(OCRResult.confidence_score)).scalar() or 0.0

        return {
            "total_cards": total,
            "pending": pending,
            "flagged": flagged,
            "approved": approved,
            "corrected": corrected,
            "average_confidence": round(float(avg_conf), 3),
            "review_progress": round((approved + corrected) / max(total, 1) * 100, 1),
        }
    finally:
        session.close()
