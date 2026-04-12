from __future__ import annotations

import json

import pytest

from southview.db.engine import get_session
from southview.db.models import Card, OCRResult, Video
from southview.ocr.errors import OCRProviderError
from southview.ocr.batch import run_ocr_for_video


def _insert_video_and_cards(file_hash: str, count: int = 1) -> tuple[str, list[str]]:
    session = get_session()
    try:
        video = Video(
            filename="test.mp4",
            filepath="/tmp/test.mp4",
            file_hash=file_hash,
            status="uploaded",
        )
        session.add(video)
        session.flush()

        card_ids: list[str] = []
        for idx in range(1, count + 1):
            card = Card(
                video_id=video.id,
                job_id=None,
                frame_number=idx,
                image_path=f"/tmp/card_{idx:04d}.png",
                sequence_index=idx,
            )
            session.add(card)
            session.flush()
            card_ids.append(card.id)
        session.commit()
        return video.id, card_ids
    finally:
        session.close()


def test_run_ocr_for_video_persists_all_structured_fields_and_raw_snapshot(tmp_db, monkeypatch):
    video_id, card_ids = _insert_video_and_cards("hash-batch-fields-1")
    card_id = card_ids[0]

    monkeypatch.setattr(
        "southview.ocr.batch.get_config",
        lambda: {
            "ocr": {
                "confidence": {
                    "review_threshold": 0.70,
                    "auto_approve": 0.85,
                }
            }
        },
    )
    monkeypatch.setattr(
        "southview.ocr.batch.process_card_min",
        lambda _image_path: {
            "raw_text": "AARON, Benjamin L.\\nDate of Death December 8, 2004",
            "card_confidence": 0.91,
            "meta": {"ocr_engine_version": "gemini:gemini-2.5-flash"},
            "fields": {
                "deceased_name": "AARON, Benjamin L.",
                "address": "123 Main St, Greenville",
                "owner": "Estate of Aaron",
                "relation": "Brother",
                "phone": "555-555-1111",
                "date_of_death": "December 8, 2004",
                "date_of_burial": "3-20-41",
                "description": "Lot 12 Range B Grave 5",
                "sex": "M",
                "age": "38",
                "grave_type": "SVC Vault",
                "grave_fee": "",
                "undertaker": "Cox",
                "board_of_health_no": "BH-889",
                "svc_no": "49,711",
            },
        },
    )

    result = run_ocr_for_video(video_id)
    assert result["processed"] == 1
    assert result["failed"] == 0

    session = get_session()
    try:
        ocr = session.query(OCRResult).filter_by(card_id=card_id).one()
        assert ocr.deceased_name == "AARON, Benjamin L."
        assert ocr.address == "123 Main St, Greenville"
        assert ocr.owner == "Estate of Aaron"
        assert ocr.relation == "Brother"
        assert ocr.phone == "555-555-1111"
        assert ocr.date_of_death == "2004-12-08"
        assert ocr.date_of_burial == "1941-03-20"
        assert ocr.description == "Lot 12 Range B Grave 5"
        assert ocr.sex == "M"
        assert ocr.age == "38"
        assert ocr.grave_type == "SVC Vault"
        assert ocr.grave_fee is None
        assert ocr.undertaker == "Cox"
        assert ocr.board_of_health_no == "BH-889"
        assert ocr.svc_no == "49,711"
        assert ocr.review_status == "approved"

        raw_snapshot = json.loads(ocr.raw_fields_json or "{}")
        assert raw_snapshot["date_of_death"] == "December 8, 2004"
        assert raw_snapshot["date_of_burial"] == "3-20-41"
        assert raw_snapshot["grave_fee"] is None
    finally:
        session.close()


def test_run_ocr_for_video_maps_legacy_field_aliases_and_preserves_unparseable_dates(tmp_db, monkeypatch):
    video_id, card_ids = _insert_video_and_cards("hash-batch-fields-2")
    card_id = card_ids[0]

    monkeypatch.setattr(
        "southview.ocr.batch.get_config",
        lambda: {"ocr": {"confidence": {"review_threshold": 0.70, "auto_approve": 0.85}}},
    )
    monkeypatch.setattr(
        "southview.ocr.batch.process_card_min",
        lambda _image_path: {
            "raw_text": "ADAMS, James",
            "card_confidence": 0.5,
            "meta": {"ocr_engine_version": "tesseract"},
            "fields": {
                "owner_name": "ADAMS, James",
                "owner_address": "404 Unknown Rd",
                "type_of_grave": "Thrasher OS",
                "date_of_death": "unknown",
            },
        },
    )

    result = run_ocr_for_video(video_id)
    assert result["processed"] == 1
    assert result["failed"] == 0

    session = get_session()
    try:
        ocr = session.query(OCRResult).filter_by(card_id=card_id).one()
        assert ocr.deceased_name == "ADAMS, James"
        assert ocr.address == "404 Unknown Rd"
        assert ocr.grave_type == "Thrasher OS"
        assert ocr.date_of_death == "unknown"

        raw_snapshot = json.loads(ocr.raw_fields_json or "{}")
        assert raw_snapshot["deceased_name"] == "ADAMS, James"
        assert raw_snapshot["address"] == "404 Unknown Rd"
        assert raw_snapshot["grave_type"] == "Thrasher OS"
        assert raw_snapshot["date_of_death"] == "unknown"
    finally:
        session.close()


def test_run_ocr_for_video_provider_error_falls_back_to_tesseract(tmp_db, monkeypatch):
    video_id, card_ids = _insert_video_and_cards("hash-batch-provider-fallback")
    card_id = card_ids[0]

    monkeypatch.setattr(
        "southview.ocr.batch.get_config",
        lambda: {
            "ocr": {
                "engine": "gemini",
                "provider_fallback_engine": "tesseract",
                "confidence": {"review_threshold": 0.70, "auto_approve": 0.85},
            }
        },
    )

    def fake_process_card_min(_image_path, *, engine_name=None):
        if engine_name == "tesseract":
            return {
                "raw_text": "fallback text",
                "card_confidence": 0.76,
                "meta": {"ocr_engine_version": "tesseract"},
                "fields": {"deceased_name": "Fallback Person"},
            }
        raise OCRProviderError("Google AI OCR request failed: HTTP 429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr("southview.ocr.batch.process_card_min", fake_process_card_min)

    result = run_ocr_for_video(video_id)
    assert result["processed"] == 1
    assert result["failed"] == 0

    session = get_session()
    try:
        ocr = session.query(OCRResult).filter_by(card_id=card_id).one()
        assert ocr.deceased_name == "Fallback Person"
        assert ocr.ocr_engine_version == "tesseract"
        assert ocr.error_message is None
    finally:
        session.close()


def test_run_ocr_for_video_provider_error_marks_one_card_and_continues(tmp_db, monkeypatch):
    video_id, card_ids = _insert_video_and_cards("hash-batch-provider-continue", count=2)

    monkeypatch.setattr(
        "southview.ocr.batch.get_config",
        lambda: {
            "ocr": {
                "engine": "gemini",
                "provider_fallback_engine": "none",
                "confidence": {"review_threshold": 0.70, "auto_approve": 0.85},
            }
        },
    )

    calls = {"count": 0}

    def fake_process_card_min(_image_path, *, engine_name=None):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OCRProviderError("Google AI OCR request failed: HTTP 429 RESOURCE_EXHAUSTED")
        return {
            "raw_text": "second card text",
            "card_confidence": 0.9,
            "meta": {"ocr_engine_version": "gemini:gemini-2.5-flash"},
            "fields": {"deceased_name": "Second Card"},
        }

    monkeypatch.setattr("southview.ocr.batch.process_card_min", fake_process_card_min)

    result = run_ocr_for_video(video_id)
    assert result["processed"] == 1
    assert result["failed"] == 1
    assert "RESOURCE_EXHAUSTED" in (result["first_error"] or "")

    session = get_session()
    try:
        first = session.query(OCRResult).filter_by(card_id=card_ids[0]).one()
        second = session.query(OCRResult).filter_by(card_id=card_ids[1]).one()
        assert first.review_status == "flagged"
        assert "RESOURCE_EXHAUSTED" in (first.error_message or "")
        assert second.deceased_name == "Second Card"
        assert second.review_status == "approved"
    finally:
        session.close()


def test_run_ocr_for_video_non_provider_error_creates_flagged_result(tmp_db, monkeypatch):
    video_id, card_ids = _insert_video_and_cards("hash-batch-non-provider-err")
    card_id = card_ids[0]

    monkeypatch.setattr(
        "southview.ocr.batch.get_config",
        lambda: {"ocr": {"confidence": {"review_threshold": 0.70, "auto_approve": 0.85}}},
    )
    monkeypatch.setattr(
        "southview.ocr.batch.process_card_min",
        lambda _image_path: (_ for _ in ()).throw(ValueError("Could not decode image")),
    )

    result = run_ocr_for_video(video_id)
    assert result["processed"] == 0
    assert result["failed"] == 1
    assert "Could not decode image" in (result["first_error"] or "")

    session = get_session()
    try:
        ocr = session.query(OCRResult).filter_by(card_id=card_id).one()
        assert ocr.review_status == "flagged"
        assert "Could not decode image" in (ocr.error_message or "")
    finally:
        session.close()
