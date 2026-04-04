from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from southview.config import get_config
from southview.db.engine import get_session
from southview.db.models import Card, OCRResult
from southview.ocr.processor_min import process_card_min


def _build_description(fields: dict) -> str | None:
    parts = []
    labels = [
        ("lot_no", "Lot"),
        ("range", "Range"),
        ("grave_no", "Grave"),
        ("section_no", "Section"),
        ("block_side", "Block"),
    ]
    for key, label in labels:
        value = fields.get(key)
        if value is None or str(value).strip() == "":
            continue
        if key == "block_side" and str(value).lower().startswith("block"):
            parts.append(str(value).strip())
        else:
            parts.append(f"{label} {str(value).strip()}")
    return ", ".join(parts) or None


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
            should_retry_existing = (
                c.ocr_result is not None
                and (
                    bool(getattr(c.ocr_result, "error_message", None))
                    or not str(getattr(c.ocr_result, "raw_text", "") or "").strip()
                )
            )
            if (c.ocr_result is not None) and (not force) and (not should_retry_existing):
                continue

            try:
                out = process_card_min(c.image_path)
                fields = out.get("fields", {}) or {}
                raw_text = out.get("raw_text", "") or ""
                conf = float(out.get("card_confidence", 0.0) or 0.0)
                rotation_degrees = int(out.get("orientation", 0) or 0)

                deceased_name = fields.get("owner_name")
                address = None
                owner = None
                relation = None
                phone = None
                date_of_death = fields.get("date_of_death")
                date_of_burial = fields.get("date_of_burial")
                description = fields.get("description") or _build_description(fields)
                sex = fields.get("sex")
                age = fields.get("age")
                grave_type = None
                grave_fee = None
                undertaker = fields.get("undertaker")
                board_of_health_no = None
                svc_no = fields.get("svc_no")

                review_status = _review_status_from_conf(
                    conf,
                    flag_threshold=flag_threshold,
                    auto_approve_threshold=auto_approve_threshold,
                    auto_approve=auto_approve,
                )

                raw_fields_json = json.dumps(
                    {
                        "deceased_name": deceased_name,
                        "date_of_death": date_of_death,
                        "date_of_burial": date_of_burial,
                        "description": description,
                        "sex": sex,
                        "age": age,
                        "undertaker": undertaker,
                        "svc_no": svc_no,
                    },
                    ensure_ascii=False,
                )

                if c.ocr_result is None:
                    r = OCRResult(
                        card_id=c.id,
                        raw_text=raw_text,
                        raw_fields_json=raw_fields_json,
                        confidence_score=conf,
                        review_status=review_status,
                        ocr_engine_version=out.get("meta", {}).get("ocr_engine_version"),
                        rotation_degrees=rotation_degrees,
                        processed_at=datetime.utcnow(),
                        deceased_name=deceased_name,
                        address=address,
                        owner=owner,
                        relation=relation,
                        phone=phone,
                        date_of_death=date_of_death,
                        date_of_burial=date_of_burial,
                        description=description,
                        sex=sex,
                        age=age,
                        grave_type=grave_type,
                        grave_fee=grave_fee,
                        undertaker=undertaker,
                        board_of_health_no=board_of_health_no,
                        svc_no=svc_no,
                        error_message=None,
                    )
                    session.add(r)
                else:
                    r = c.ocr_result
                    r.raw_text = raw_text
                    r.raw_fields_json = raw_fields_json
                    r.confidence_score = conf
                    r.review_status = review_status
                    r.ocr_engine_version = out.get("meta", {}).get("ocr_engine_version")
                    r.rotation_degrees = rotation_degrees
                    r.processed_at = datetime.utcnow()
                    r.deceased_name = deceased_name
                    r.address = address
                    r.owner = owner
                    r.relation = relation
                    r.phone = phone
                    r.date_of_death = date_of_death
                    r.date_of_burial = date_of_burial
                    r.description = description
                    r.sex = sex
                    r.age = age
                    r.grave_type = grave_type
                    r.grave_fee = grave_fee
                    r.undertaker = undertaker
                    r.board_of_health_no = board_of_health_no
                    r.svc_no = svc_no
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
                        rotation_degrees=0,
                        processed_at=datetime.utcnow(),
                        deceased_name=None,
                        address=None,
                        owner=None,
                        relation=None,
                        phone=None,
                        date_of_death=None,
                        date_of_burial=None,
                        description=None,
                        sex=None,
                        age=None,
                        grave_type=None,
                        grave_fee=None,
                        undertaker=None,
                        board_of_health_no=None,
                        svc_no=None,
                        error_message=msg,
                    )
                    session.add(r)
                else:
                    r = c.ocr_result
                    r.error_message = msg
                    r.confidence_score = 0.0
                    r.review_status = "flagged"
                    r.rotation_degrees = 0
                    r.processed_at = datetime.utcnow()
                    r.deceased_name = None
                    r.address = None
                    r.owner = None
                    r.relation = None
                    r.phone = None
                    r.date_of_death = None
                    r.date_of_burial = None
                    r.description = None
                    r.sex = None
                    r.age = None
                    r.grave_type = None
                    r.grave_fee = None
                    r.undertaker = None
                    r.board_of_health_no = None
                    r.svc_no = None

                session.commit()

        return {"video_id": video_id, "processed": processed, "failed": failed}

    finally:
        session.close()
