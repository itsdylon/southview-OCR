from __future__ import annotations

import sqlite3

from southview.db.engine import get_engine, init_db


def test_init_db_sets_sqlite_busy_timeout(tmp_path):
    db_path = tmp_path / "busy-timeout.db"

    init_db(db_path)

    with get_engine().connect() as conn:
        busy_timeout = conn.exec_driver_sql("PRAGMA busy_timeout").scalar_one()

    assert busy_timeout == 5000


def test_init_db_adds_missing_jobs_status_index_for_existing_databases(tmp_path):
    db_path = tmp_path / "legacy-indexes.db"

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE videos (
                id VARCHAR(36) PRIMARY KEY,
                filename VARCHAR NOT NULL,
                filepath VARCHAR,
                file_hash VARCHAR(64) NOT NULL UNIQUE,
                status VARCHAR(20) NOT NULL DEFAULT 'uploaded',
                duration_seconds FLOAT,
                resolution_w INTEGER,
                resolution_h INTEGER,
                fps FLOAT,
                frame_count INTEGER,
                file_size_bytes INTEGER,
                upload_timestamp DATETIME NOT NULL,
                metadata_json TEXT
            );

            CREATE TABLE jobs (
                id VARCHAR(36) PRIMARY KEY,
                video_id VARCHAR(36) NOT NULL,
                job_type VARCHAR(30) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'queued',
                progress INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                created_at DATETIME NOT NULL,
                started_at DATETIME,
                completed_at DATETIME,
                FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            """
            INSERT INTO videos (
                id, filename, filepath, file_hash, status, upload_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("v1", "video.mp4", "/tmp/video.mp4", "hash-v1", "uploaded", "2026-04-12T00:00:00"),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                id, video_id, job_type, status, progress, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("j1", "v1", "full_pipeline", "queued", 0, "2026-04-12T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    init_db(db_path)

    verify = sqlite3.connect(db_path)
    try:
        job_indexes = {
            row[1]
            for row in verify.execute("PRAGMA index_list('jobs')").fetchall()
        }
        card_indexes = {
            row[1]
            for row in verify.execute("PRAGMA index_list('cards')").fetchall()
        }
        assert "ix_jobs_status" in job_indexes
        assert "ix_cards_video_id" in card_indexes
        assert verify.execute("SELECT id, status FROM jobs WHERE id = 'j1'").fetchone() == ("j1", "queued")
    finally:
        verify.close()
