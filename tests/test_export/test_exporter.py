"""Tests for CSV/JSON export."""

from __future__ import annotations

import csv
import io
import json

from southview.db.engine import get_session
from southview.db.models import Card, OCRResult, Video
from southview.export.exporter import export_csv, export_json


def _seed_export_row() -> None:
    session = get_session()
    try:
        video = Video(
            filename="export.mp4",
            filepath="/tmp/export.mp4",
            file_hash="hash-export-1",
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
            raw_text="Sample raw text",
            raw_fields_json='{"deceased_name":"SMITH, John"}',
            confidence_score=0.8,
            review_status="approved",
            deceased_name="SMITH, John",
            address="100 Elm St",
            owner="Smith Estate",
            relation="Daughter",
            phone="555-2000",
            date_of_death="2021-10-30",
            date_of_burial="2021-11-02",
            description="Section A",
            sex="M",
            age="78",
            grave_type="Single",
            grave_fee="$200",
            undertaker="Heritage",
            board_of_health_no="BH-10",
            svc_no="A-102",
        )
        session.add(ocr)
        session.commit()
    finally:
        session.close()


def test_export_csv_includes_full_structured_fields(tmp_db):
    _seed_export_row()

    output = export_csv()
    reader = csv.DictReader(io.StringIO(output))
    rows = list(reader)

    assert len(rows) == 1
    row = rows[0]
    assert row["deceased_name"] == "SMITH, John"
    assert row["address"] == "100 Elm St"
    assert row["owner"] == "Smith Estate"
    assert row["relation"] == "Daughter"
    assert row["phone"] == "555-2000"
    assert row["date_of_death"] == "2021-10-30"
    assert row["date_of_burial"] == "2021-11-02"
    assert row["description"] == "Section A"
    assert row["sex"] == "M"
    assert row["age"] == "78"
    assert row["grave_type"] == "Single"
    assert row["grave_fee"] == "$200"
    assert row["undertaker"] == "Heritage"
    assert row["board_of_health_no"] == "BH-10"
    assert row["svc_no"] == "A-102"


def test_export_json_includes_full_structured_fields(tmp_db):
    _seed_export_row()

    output = export_json()
    rows = json.loads(output)

    assert len(rows) == 1
    row = rows[0]
    assert row["deceased_name"] == "SMITH, John"
    assert row["address"] == "100 Elm St"
    assert row["grave_type"] == "Single"
    assert row["board_of_health_no"] == "BH-10"
