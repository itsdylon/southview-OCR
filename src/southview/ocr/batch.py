from __future__ import annotations

import re
import json
import logging
import time
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from southview.config import get_config
from southview.db.engine import get_session
from southview.db.models import Card, OCRResult
from southview.ocr.engine import get_ocr_engine_name
from southview.ocr.errors import OCRProviderError
from southview.ocr.parser_min import standardize_date_to_iso
from southview.ocr.processor_min import process_card_min

logger = logging.getLogger(__name__)

STRUCTURED_FIELDS = [
    "deceased_name",
    "address",
    "owner",
    "relation",
    "phone",
    "date_of_death",
    "date_of_burial",
    "description",
    "sex",
    "age",
    "grave_type",
    "grave_fee",
    "undertaker",
    "board_of_health_no",
    "svc_no",
]

LEGACY_FIELD_ALIASES = {
    "owner_name": "deceased_name",
    "owner_address": "address",
    "type_of_grave": "grave_type",
}

DATE_FIELDS = {"date_of_death", "date_of_burial"}
_TWO_DIGIT_YEAR_DATE_RX = re.compile(
    r"(?:\b\d{1,2}[/-]\d{1,2}[/-]\d{2}\b)|(?:\b[A-Za-z]+\s+\d{1,2},\s*\d{2}\b)",
    re.IGNORECASE,
)


def _clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _canonical_raw_fields(fields: dict[str, Any]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}

    alias_to_canonical = {}
    for legacy_key, canonical_key in LEGACY_FIELD_ALIASES.items():
        alias_to_canonical.setdefault(canonical_key, []).append(legacy_key)

    for key in STRUCTURED_FIELDS:
        if key in fields:
            out[key] = _clean_optional_text(fields.get(key))
            continue

        alias_keys = alias_to_canonical.get(key, [])
        alias_value = None
        for alias_key in alias_keys:
            if alias_key in fields:
                alias_value = fields.get(alias_key)
                break
        out[key] = _clean_optional_text(alias_value)

    return out


def _normalized_db_fields(raw_fields: dict[str, str | None]) -> dict[str, str | None]:
    out = dict(raw_fields)
    for key in DATE_FIELDS:
        raw_value = out.get(key)
        if raw_value is None:
            continue
        iso = standardize_date_to_iso(raw_value)
        if not iso:
            out[key] = raw_value
            continue

        # Prefer historical interpretation for ambiguous two-digit years.
        if _TWO_DIGIT_YEAR_DATE_RX.search(raw_value):
            year = int(iso[:4])
            if year > datetime.utcnow().year + 1:
                iso = f"{year - 100:04d}{iso[4:]}"
        out[key] = iso
    return out


def _apply_structured_fields(record: OCRResult, values: dict[str, str | None]) -> None:
    for key in STRUCTURED_FIELDS:
        setattr(record, key, values.get(key))


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


def _provider_fallback_engine() -> str | None:
    cfg = get_config().get("ocr", {})
    primary = get_ocr_engine_name()
    fallback = str(cfg.get("provider_fallback_engine", "tesseract")).strip().lower()
    if primary != "gemini":
        return None
    if fallback in {"", "none", primary}:
        return None
    return fallback


def _persist_successful_ocr_result(
    session,
    card: Card,
    out: dict[str, Any],
    *,
    flag_threshold: float,
    auto_approve_threshold: float,
    auto_approve: bool,
) -> None:
    fields = out.get("fields", {}) or {}
    raw_text = out.get("raw_text", "") or ""
    conf = float(out.get("card_confidence", 0.0) or 0.0)
    ocr_engine_version = (out.get("meta", {}) or {}).get("ocr_engine_version")
    raw_structured_fields = _canonical_raw_fields(fields)
    db_structured_fields = _normalized_db_fields(raw_structured_fields)

    review_status = _review_status_from_conf(
        conf,
        flag_threshold=flag_threshold,
        auto_approve_threshold=auto_approve_threshold,
        auto_approve=auto_approve,
    )

    raw_fields_json = json.dumps(
        raw_structured_fields,
        ensure_ascii=False,
    )

    if card.ocr_result is None:
        record = OCRResult(
            card_id=card.id,
            raw_text=raw_text,
            raw_fields_json=raw_fields_json,
            confidence_score=conf,
            review_status=review_status,
            ocr_engine_version=ocr_engine_version,
            processed_at=datetime.utcnow(),
            error_message=None,
            **db_structured_fields,
        )
        session.add(record)
    else:
        record = card.ocr_result
        record.raw_text = raw_text
        record.raw_fields_json = raw_fields_json
        record.confidence_score = conf
        record.review_status = review_status
        record.ocr_engine_version = ocr_engine_version
        record.processed_at = datetime.utcnow()
        record.error_message = None
        _apply_structured_fields(record, db_structured_fields)

    session.commit()


def _persist_failed_ocr_result(session, card: Card, message: str) -> None:
    if card.ocr_result is None:
        empty_structured = {key: None for key in STRUCTURED_FIELDS}
        record = OCRResult(
            card_id=card.id,
            raw_text="",
            raw_fields_json=None,
            confidence_score=0.0,
            review_status="flagged",
            processed_at=datetime.utcnow(),
            error_message=message,
            **empty_structured,
        )
        session.add(record)
    else:
        record = card.ocr_result
        record.error_message = message
        record.confidence_score = 0.0
        record.review_status = "flagged"
        record.processed_at = datetime.utcnow()
        _apply_structured_fields(record, {key: None for key in STRUCTURED_FIELDS})

    session.commit()


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
    provider_fallback_engine = _provider_fallback_engine()
    session = get_session()
    processed = 0
    failed = 0
    first_error: str | None = None
    started = time.perf_counter()

    try:
        stmt = (
            select(Card)
            .options(selectinload(Card.ocr_result))
            .where(Card.video_id == video_id)
            .order_by(Card.sequence_index.asc())
        )
        cards = list(session.execute(stmt).scalars().all())
        total_cards = len(cards)
        cards_to_process = sum(1 for c in cards if force or c.ocr_result is None)
        logger.info(
            "OCR batch start: video_id=%s total_cards=%d to_process=%d force=%s",
            video_id,
            total_cards,
            cards_to_process,
            force,
        )

        processed_or_failed = 0
        for c in cards:
            if (c.ocr_result is not None) and (not force):
                continue

            card_started = time.perf_counter()
            try:
                out = process_card_min(c.image_path)
                _persist_successful_ocr_result(
                    session,
                    c,
                    out,
                    flag_threshold=flag_threshold,
                    auto_approve_threshold=auto_approve_threshold,
                    auto_approve=auto_approve,
                )
                processed += 1
                processed_or_failed += 1

                elapsed_card = time.perf_counter() - card_started
                logger.debug(
                    "OCR card processed: video_id=%s card_id=%s elapsed=%.2fs",
                    video_id,
                    c.id,
                    elapsed_card,
                )

                if cards_to_process > 0 and (processed_or_failed % 25 == 0 or processed_or_failed == cards_to_process):
                    elapsed = time.perf_counter() - started
                    avg = elapsed / processed_or_failed if processed_or_failed else 0.0
                    remaining = cards_to_process - processed_or_failed
                    eta = remaining * avg
                    logger.info(
                        (
                            "OCR progress: video_id=%s done=%d/%d "
                            "(processed=%d failed=%d) elapsed=%.1fs avg/card=%.2fs eta=%.1fs"
                        ),
                        video_id,
                        processed_or_failed,
                        cards_to_process,
                        processed,
                        failed,
                        elapsed,
                        avg,
                        eta,
                    )

            except OCRProviderError as e:
                session.rollback()
                msg = str(e)
                if first_error is None:
                    first_error = msg
                if provider_fallback_engine is not None:
                    logger.warning(
                        "OCR provider failure for card %s; retrying with fallback engine %s: %s",
                        c.id,
                        provider_fallback_engine,
                        msg,
                    )
                    try:
                        fallback_out = process_card_min(c.image_path, engine_name=provider_fallback_engine)
                        _persist_successful_ocr_result(
                            session,
                            c,
                            fallback_out,
                            flag_threshold=flag_threshold,
                            auto_approve_threshold=auto_approve_threshold,
                            auto_approve=auto_approve,
                        )
                        processed += 1
                        processed_or_failed += 1
                        logger.info(
                            "OCR fallback succeeded: video_id=%s card_id=%s engine=%s",
                            video_id,
                            c.id,
                            provider_fallback_engine,
                        )
                        continue
                    except Exception as fallback_exc:
                        session.rollback()
                        msg = f"{msg}; fallback {provider_fallback_engine} failed: {fallback_exc}"

                failed += 1
                processed_or_failed += 1
                _persist_failed_ocr_result(session, c, msg)
                logger.error(
                    (
                        "OCR provider failure recorded: video_id=%s card_id=%s elapsed=%.2fs "
                        "processed=%d failed=%d error=%s"
                    ),
                    video_id,
                    c.id,
                    time.perf_counter() - card_started,
                    processed,
                    failed,
                    msg,
                )
                continue

            except Exception as e:
                failed += 1
                processed_or_failed += 1
                msg = str(e)
                if first_error is None:
                    first_error = msg
                logger.warning("OCR failed for card %s (%s): %s", c.id, c.image_path, msg)
                _persist_failed_ocr_result(session, c, msg)
                elapsed_card = time.perf_counter() - card_started
                logger.warning(
                    "OCR card failed: video_id=%s card_id=%s elapsed=%.2fs error=%s",
                    video_id,
                    c.id,
                    elapsed_card,
                    msg,
                )

        total_elapsed = time.perf_counter() - started
        avg_per_attempt = total_elapsed / (processed + failed) if (processed + failed) else 0.0
        logger.info(
            (
                "OCR batch complete: video_id=%s processed=%d failed=%d "
                "elapsed=%.1fs avg/attempt=%.2fs"
            ),
            video_id,
            processed,
            failed,
            total_elapsed,
            avg_per_attempt,
        )
        return {
            "video_id": video_id,
            "processed": processed,
            "failed": failed,
            "first_error": first_error,
        }

    finally:
        session.close()
