from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import joinedload

from southview.config import get_config
from southview.db.engine import get_session
from southview.db.models import Card, OCRResult, STRUCTURED_OCR_FIELDS

ALLOWED_STRUCTURED_FIELDS = set(STRUCTURED_OCR_FIELDS)


def _parse_status_in(status_in: str | None) -> list[str] | None:
    if not status_in:
        return None
    items = [s.strip().lower() for s in status_in.split(",") if s.strip()]
    return items or None


def list_cards(
    *,
    video_id: str | None = None,
    status: str | None = None,
    status_in: str | None = None,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    q: str | None = None,
    dod_from: str | None = None,
    dod_to: str | None = None,
    sort: str = "confidence",
    page: int = 1,
    per_page: int = 50,
) -> dict[str, Any]:
    """
    Returns paginated result with keys: cards, total, page, per_page, pages.
    """
    session = get_session()
    try:
        stmt = (
            select(Card)
            .options(joinedload(Card.ocr_result))
        )

        filters = []

        if video_id:
            filters.append(Card.video_id == video_id)

        # legacy single-status filter (keep)
        if status:
            filters.append(OCRResult.review_status == status.lower())

        # new multi-status filter
        statuses = _parse_status_in(status_in)
        if statuses:
            filters.append(OCRResult.review_status.in_(statuses))

        if min_confidence is not None:
            filters.append(OCRResult.confidence_score >= float(min_confidence))
        if max_confidence is not None:
            filters.append(OCRResult.confidence_score <= float(max_confidence))

        if q:
            like = f"%{q.strip()}%"
            filters.append(func.lower(OCRResult.deceased_name).like(func.lower(like)))

        # These assume date_of_death is stored as ISO ("YYYY-MM-DD") or None.
        if dod_from:
            filters.append(OCRResult.date_of_death >= dod_from)
        if dod_to:
            filters.append(OCRResult.date_of_death <= dod_to)

        if filters:
            stmt = stmt.join(OCRResult, OCRResult.card_id == Card.id).where(and_(*filters))
        else:
            stmt = stmt.join(OCRResult, OCRResult.card_id == Card.id)

        # total count (before pagination)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = session.execute(count_stmt).scalar_one()

        # sorting
        if sort == "sequence_index":
            stmt = stmt.order_by(Card.sequence_index.asc())
        else:
            # default: confidence worst-first for review
            stmt = stmt.order_by(OCRResult.confidence_score.asc(), Card.sequence_index.asc())

        # pagination
        offset = (page - 1) * per_page
        stmt = stmt.offset(offset).limit(per_page)

        cards = list(session.execute(stmt).scalars().all())

        rows: list[dict[str, Any]] = []
        for c in cards:
            r = c.ocr_result
            row = {
                "card_id": c.id,
                "video_id": c.video_id,
                "sequence_index": c.sequence_index,
                "frame_number": c.frame_number,
                "image_path": c.image_path,
                "review_status": r.review_status if r else None,
                "confidence_score": float(r.confidence_score) if r else None,
                "error_message": getattr(r, "error_message", None) if r else None,
            }
            for field in STRUCTURED_OCR_FIELDS:
                row[field] = getattr(r, field, None) if r else None
            rows.append(row)

        pages = max(1, -(-total // per_page))  # ceiling division
        return {
            "cards": rows,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }
    finally:
        session.close()


def get_card_detail(card_id: str) -> dict[str, Any]:
    session = get_session()
    try:
        stmt = select(Card).options(joinedload(Card.ocr_result)).where(Card.id == card_id)
        c = session.execute(stmt).scalar_one_or_none()
        if not c:
            raise ValueError(f"Card not found: {card_id}")
        r = c.ocr_result
        if not r:
            raise ValueError(f"OCR result missing for card: {card_id}")

        return {
            "card_id": c.id,
            "video_id": c.video_id,
            "sequence_index": c.sequence_index,
            "frame_number": c.frame_number,
            "image_path": c.image_path,
            "raw_text": r.raw_text,
            "raw_fields_json": getattr(r, "raw_fields_json", None),
            "confidence_score": float(r.confidence_score),
            "review_status": r.review_status,
            "reviewed_by": r.reviewed_by,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "error_message": getattr(r, "error_message", None),
            **{field: getattr(r, field, None) for field in STRUCTURED_OCR_FIELDS},
        }
    finally:
        session.close()


def submit_review(
    card_id: str,
    *,
    fields: dict[str, Any] | None,
    status: str,
    reviewed_by: str | None = None,
    structured_fields: dict | None = None,
) -> dict[str, Any]:
    """
    Only allow:
      - approved (no field edits)
      - corrected (field edits present)
    """
    status = status.lower().strip()
    if status not in ("approved", "corrected"):
        raise ValueError("status must be 'approved' or 'corrected'")

    fields = fields or {}


    session = get_session()
    try:
        r = session.execute(select(OCRResult).where(OCRResult.card_id == card_id)).scalar_one_or_none()
        if not r:
            raise ValueError(f"OCR result not found for card: {card_id}")

        has_structured_updates = bool(structured_fields)
        has_dict_updates = bool(fields)
        has_any_updates = has_dict_updates or has_structured_updates

        # validate edit rules
        if has_any_updates and status != "corrected":
            raise ValueError("If fields are provided, status must be 'corrected'")
        if (not has_any_updates) and status != "approved":
            raise ValueError("If no fields are provided, status must be 'approved'")

        # apply edits
        for k, v in fields.items():
            if not hasattr(r, k):
                raise ValueError(f"Unknown field: {k}")
            setattr(r, k, v)

        r.review_status = status
        r.reviewed_by = reviewed_by
        r.reviewed_at = datetime.utcnow()

        # Apply structured field updates
        if structured_fields:
            for key, value in structured_fields.items():
                if key in ALLOWED_STRUCTURED_FIELDS:
                    setattr(r, key, value)


        session.commit()

        return {
            "card_id": card_id,
            "review_status": r.review_status,
            "reviewed_by": r.reviewed_by,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            **{field: getattr(r, field, None) for field in STRUCTURED_OCR_FIELDS},
        }
    finally:
        session.close()


def batch_approve(card_ids: list[str], *, reviewed_by: str | None = None) -> dict[str, Any]:
    session = get_session()
    try:
        rs = list(session.execute(select(OCRResult).where(OCRResult.card_id.in_(card_ids))).scalars().all())
        for r in rs:
            r.review_status = "approved"
            r.reviewed_by = reviewed_by
            r.reviewed_at = datetime.utcnow()
        session.commit()
        return {"updated": len(rs), "status": "approved"}
    finally:
        session.close()


def get_review_stats(*, video_id: str | None = None) -> dict[str, Any]:
    """
    Returns counts for:
      flagged, pending, auto_approved, approved, corrected, total
    """
    cfg = get_config()
    auto_thr = float(cfg["ocr"]["confidence"]["auto_approve"])

    session = get_session()
    try:
        base = select(OCRResult).join(Card, Card.id == OCRResult.card_id)
        if video_id:
            base = base.where(Card.video_id == video_id)

        # total
        total = session.execute(select(func.count()).select_from(base.subquery())).scalar_one()

        # status counts
        def _count_where(where_clause):
            q = select(func.count()).select_from(OCRResult).join(Card, Card.id == OCRResult.card_id)
            if video_id:
                q = q.where(Card.video_id == video_id)
            q = q.where(where_clause)
            return session.execute(q).scalar_one()

        flagged = _count_where(OCRResult.review_status == "flagged")
        pending = _count_where(OCRResult.review_status == "pending")
        approved = _count_where(OCRResult.review_status == "approved")
        corrected = _count_where(OCRResult.review_status == "corrected")
        auto_approved = _count_where(and_(OCRResult.review_status == "approved", OCRResult.confidence_score >= auto_thr))

        return {
            "video_id": video_id,
            "counts": {
                "flagged": int(flagged),
                "pending": int(pending),
                "auto_approved": int(auto_approved),
                "approved": int(approved),
                "corrected": int(corrected),
                "total": int(total),
            },
            "auto_approve_threshold": auto_thr,
        }
    finally:
        session.close()
