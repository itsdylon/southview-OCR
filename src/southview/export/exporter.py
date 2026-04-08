"""CSV and JSON export of card data."""

import csv
import json
from io import StringIO
from pathlib import Path

from sqlalchemy.orm import joinedload

from southview.db.engine import get_session
from southview.db.models import Card, OCRResult, STRUCTURED_OCR_FIELDS, Video


def _query_cards(video_id: str | None = None, status: str | None = None) -> list[dict]:
    """Query cards with their OCR results, applying optional filters."""
    session = get_session()
    try:
        query = (
            session.query(Card)
            .options(joinedload(Card.ocr_result), joinedload(Card.video))
        )

        if video_id:
            query = query.filter(Card.video_id == video_id)
        if status:
            query = query.join(OCRResult).filter(OCRResult.review_status == status)

        query = query.order_by(Card.video_id, Card.sequence_index)
        cards = query.all()

        results = []
        for card in cards:
            ocr = card.ocr_result
            row = {
                "card_id": card.id,
                "video_filename": card.video.filename if card.video else "",
                "video_id": card.video_id,
                "sequence_index": card.sequence_index,
                "raw_text": ocr.raw_text if ocr else "",
                "confidence_score": ocr.confidence_score if ocr else 0.0,
                "review_status": ocr.review_status if ocr else "",
                "reviewed_by": ocr.reviewed_by if ocr else "",
                "image_path": card.image_path,
            }
            for field in STRUCTURED_OCR_FIELDS:
                row[field] = getattr(ocr, field, "") if ocr else ""
            results.append(row)

        return results
    finally:
        session.close()


def export_csv(
    output_path: str | Path | None = None,
    video_id: str | None = None,
    status: str | None = None,
) -> str:
    """Export card data as CSV. Returns CSV string if no output_path given."""
    rows = _query_cards(video_id=video_id, status=status)
    if not rows:
        return ""

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

    csv_str = output.getvalue()

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(csv_str)

    return csv_str


def export_json(
    output_path: str | Path | None = None,
    video_id: str | None = None,
    status: str | None = None,
) -> str:
    """Export card data as JSON. Returns JSON string if no output_path given."""
    rows = _query_cards(video_id=video_id, status=status)

    json_str = json.dumps(rows, indent=2)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json_str)

    return json_str
