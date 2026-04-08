from __future__ import annotations

import sqlite3

from southview.db.engine import init_db


CANONICAL_FIELDS = [
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


def test_init_db_adds_missing_ocr_structured_columns_without_data_loss(tmp_path):
    db_path = tmp_path / "legacy.db"

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE ocr_results (
                id VARCHAR(36) PRIMARY KEY,
                card_id VARCHAR(36) UNIQUE,
                raw_text TEXT NOT NULL,
                raw_fields_json TEXT,
                confidence_score FLOAT NOT NULL,
                word_confidences TEXT,
                ocr_engine_version VARCHAR,
                processed_at DATETIME NOT NULL,
                review_status VARCHAR(20) NOT NULL,
                reviewed_by VARCHAR,
                reviewed_at DATETIME,
                error_message TEXT,
                deceased_name VARCHAR,
                date_of_death VARCHAR
            );
            """
        )
        conn.execute(
            """
            INSERT INTO ocr_results (
                id, card_id, raw_text, raw_fields_json, confidence_score,
                processed_at, review_status, deceased_name, date_of_death
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "r1",
                "c1",
                "raw",
                '{"deceased_name":"AARON, Benjamin L."}',
                0.93,
                "2026-04-08T00:00:00",
                "pending",
                "AARON, Benjamin L.",
                "2004-12-08",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    init_db(db_path)

    verify = sqlite3.connect(db_path)
    try:
        columns = {
            row[1]
            for row in verify.execute("PRAGMA table_info('ocr_results')").fetchall()
        }
        for field in CANONICAL_FIELDS:
            assert field in columns

        row = verify.execute(
            "SELECT deceased_name, date_of_death, grave_type, undertaker FROM ocr_results WHERE id = 'r1'"
        ).fetchone()
        assert row == ("AARON, Benjamin L.", "2004-12-08", None, None)
    finally:
        verify.close()
