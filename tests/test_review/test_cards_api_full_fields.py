from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from southview.api.app import create_app
from southview.db.engine import get_session
from southview.db.models import Card, OCRResult, Video


@pytest.fixture
def client(tmp_path, tmp_db, tmp_config):
    config = tmp_config
    with patch("southview.api.app.init_db"), patch("southview.api.app.get_config", return_value=config):
        app = create_app()
        with TestClient(app) as c:
            yield c


def _seed_card_with_full_ocr() -> tuple[str, str]:
    session = get_session()
    try:
        video = Video(
            filename="seed.mp4",
            filepath="/tmp/seed.mp4",
            file_hash="hash-cards-api-1",
            status="completed",
        )
        session.add(video)
        session.flush()

        card = Card(
            video_id=video.id,
            frame_number=10,
            image_path="/tmp/card_0001.png",
            sequence_index=1,
        )
        session.add(card)
        session.flush()

        ocr = OCRResult(
            card_id=card.id,
            raw_text="AARON, Benjamin L.",
            raw_fields_json='{"deceased_name":"AARON, Benjamin L."}',
            confidence_score=0.88,
            review_status="pending",
            deceased_name="AARON, Benjamin L.",
            address="123 Main St",
            owner="Estate",
            relation="Son",
            phone="555-1010",
            date_of_death="2004-12-08",
            date_of_burial="2004-12-12",
            description="Lot 1",
            sex="M",
            age="38",
            grave_type="SVC Vault",
            grave_fee="$150",
            undertaker="Cox",
            board_of_health_no="BH-12",
            svc_no="49,711",
        )
        session.add(ocr)
        session.commit()
        return video.id, card.id
    finally:
        session.close()


def test_cards_list_includes_full_structured_fields(client):
    video_id, card_id = _seed_card_with_full_ocr()

    resp = client.get(f"/api/cards?video_id={video_id}")
    assert resp.status_code == 200

    payload = resp.json()
    assert payload["total"] == 1
    card = payload["cards"][0]
    assert card["id"] == card_id
    assert card["deceased_name"] == "AARON, Benjamin L."
    assert card["address"] == "123 Main St"
    assert card["owner"] == "Estate"
    assert card["relation"] == "Son"
    assert card["phone"] == "555-1010"
    assert card["date_of_death"] == "2004-12-08"
    assert card["date_of_burial"] == "2004-12-12"
    assert card["description"] == "Lot 1"
    assert card["sex"] == "M"
    assert card["age"] == "38"
    assert card["grave_type"] == "SVC Vault"
    assert card["grave_fee"] == "$150"
    assert card["undertaker"] == "Cox"
    assert card["board_of_health_no"] == "BH-12"
    assert card["svc_no"] == "49,711"


def test_review_update_round_trip_with_structured_fields_only(client):
    _, card_id = _seed_card_with_full_ocr()

    update = {
        "status": "corrected",
        "deceased_name": "AARON, Ben",
        "grave_type": "Thrasher OS",
        "board_of_health_no": "BH-99",
    }
    resp = client.put(f"/api/cards/{card_id}/review", json=update)
    assert resp.status_code == 200

    detail = client.get(f"/api/cards/{card_id}")
    assert detail.status_code == 200

    ocr = detail.json()["ocr"]
    assert ocr["review_status"] == "corrected"
    assert ocr["deceased_name"] == "AARON, Ben"
    assert ocr["grave_type"] == "Thrasher OS"
    assert ocr["board_of_health_no"] == "BH-99"
