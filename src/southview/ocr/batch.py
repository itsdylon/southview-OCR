from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from southview.config import get_config
from southview.db.engine import get_session
from southview.db.models import Card, OCRResult
from southview.ocr.processor_min import process_card_min


def _review_status_from_conf(
    conf: float,
    *,
    flag_threshold: float,
    auto_approve_threshold: float,
    auto_approve: bool,
) -> str:
    if conf < flag_threshold:
        return "flagged"
    if auto_approve and conf >= auto_approve_threshold:
        return "approved"
    return "pending"


def run_ocr_for_video(
    video_id: str,
    *,
    flag_threshold: float | None = None,
    auto_approve_threshold: float | None = None,
    auto_approve: bool = True,
    force: bool = False,
) -> dict:
    # Read thresholds from config, fall back to sensible defaults
    conf_config = get_config().get("ocr", {}).get("confidence", {})
    if flag_threshold is None:
        flag_threshold = conf_config.get("review_threshold", 0.70)
    if auto_approve_threshold is None:
        auto_approve_threshold = conf_config.get("auto_approve", 0.85)
    session = get_session()
    processed = 0
    failed = 0

    try:
        stmt = (
            select(Card)
            .options(selectinload(Card.ocr_result))
            .where(Card.video_id == video_id)
            .order_by(Card.sequence_index.asc())
        )
        cards = list(session.execute(stmt).scalars().all())

        for c in cards:
            if (c.ocr_result is not None) and (not force):
                continue

            try:
                out = process_card_min(c.image_path)
                fields = out.get("fields", {}) or {}
                raw_text = out.get("raw_text", "") or ""
                conf = float(out.get("card_confidence", 0.0) or 0.0)

                deceased_name = fields.get("owner_name")
                date_of_death = fields.get("date_of_death")

                review_status = _review_status_from_conf(
                    conf,
                    flag_threshold=flag_threshold,
                    auto_approve_threshold=auto_approve_threshold,
                    auto_approve=auto_approve,
                )

                raw_fields_json = json.dumps(
                    {"deceased_name": deceased_name, "date_of_death": date_of_death},
                    ensure_ascii=False,
                )

                if c.ocr_result is None:
                    r = OCRResult(
                        card_id=c.id,
                        raw_text=raw_text,
                        raw_fields_json=raw_fields_json,
                        confidence_score=conf,
                        review_status=review_status,
                        processed_at=datetime.utcnow(),
                        deceased_name=deceased_name,
                        date_of_death=date_of_death,
                        error_message=None,
                    )
                    session.add(r)
                else:
                    r = c.ocr_result
                    r.raw_text = raw_text
                    r.raw_fields_json = raw_fields_json
                    r.confidence_score = conf
                    r.review_status = review_status
                    r.processed_at = datetime.utcnow()
                    r.deceased_name = deceased_name
                    r.date_of_death = date_of_death
                    r.error_message = None

                session.commit()
                processed += 1

            except Exception as e:
                failed += 1
                msg = str(e)

                if c.ocr_result is None:
                    r = OCRResult(
                        card_id=c.id,
                        raw_text="",
                        raw_fields_json=None,
                        confidence_score=0.0,
                        review_status="flagged",
                        processed_at=datetime.utcnow(),
                        deceased_name=None,
                        date_of_death=None,
                        error_message=msg,
                    )
                    session.add(r)
                else:
                    r = c.ocr_result
                    r.error_message = msg
                    r.confidence_score = 0.0
                    r.review_status = "flagged"
                    r.processed_at = datetime.utcnow()
                    r.deceased_name = None
                    r.date_of_death = None

                session.commit()

        return {"video_id": video_id, "processed": processed, "failed": failed}

    finally:
        session.close()
