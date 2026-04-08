# src/southview/db/engine.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

_ENGINE: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def init_db(db_path: str | Path) -> Engine:
    """
    Initialize SQLite engine + sessionmaker. Enables WAL mode.
    Call this once at app startup.
    """
    global _ENGINE, _SessionLocal

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    url = f"sqlite:///{db_path}"
    engine = create_engine(
        url,
        future=True,
        echo=False,
        connect_args={"check_same_thread": False},  # FastAPI threads
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.close()

    _ENGINE = engine
    _SessionLocal = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False, future=True)

    # create tables
    from southview.db.models import Base  # noqa
    Base.metadata.create_all(bind=_ENGINE)

    # migrations: make videos.filepath nullable (SQLite requires table rebuild)
    _migrate_filepath_nullable(engine)
    # migrations: add newly supported structured OCR columns
    _migrate_ocr_results_structured_columns(engine)

    return _ENGINE


def _migrate_filepath_nullable(engine: Engine) -> None:
    """One-time migration: allow videos.filepath to be NULL."""
    with engine.connect() as conn:
        # Check if filepath column is still NOT NULL
        rows = conn.exec_driver_sql(
            "SELECT [notnull] FROM pragma_table_info('videos') WHERE name='filepath'"
        ).fetchone()
        if rows and rows[0] == 1:
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            conn.exec_driver_sql("""
                CREATE TABLE videos_new AS SELECT * FROM videos
            """)
            conn.exec_driver_sql("DROP TABLE videos")
            conn.exec_driver_sql("""
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
                )
            """)
            conn.exec_driver_sql("INSERT INTO videos SELECT * FROM videos_new")
            conn.exec_driver_sql("DROP TABLE videos_new")
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            conn.commit()


def _table_columns(conn, table_name: str) -> set[str]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info('{table_name}')").fetchall()
    return {str(r[1]) for r in rows}


def _migrate_ocr_results_structured_columns(engine: Engine) -> None:
    """
    Additive migration: ensure ocr_results contains the canonical structured fields.
    This is idempotent and does not rewrite existing rows.
    """
    column_types = {
        "deceased_name": "VARCHAR",
        "address": "VARCHAR",
        "owner": "VARCHAR",
        "relation": "VARCHAR",
        "phone": "VARCHAR",
        "date_of_death": "VARCHAR",
        "date_of_burial": "VARCHAR",
        "description": "TEXT",
        "sex": "VARCHAR",
        "age": "VARCHAR",
        "grave_type": "VARCHAR",
        "grave_fee": "VARCHAR",
        "undertaker": "VARCHAR",
        "board_of_health_no": "VARCHAR",
        "svc_no": "VARCHAR",
    }

    with engine.connect() as conn:
        existing_tables = {
            str(r[0])
            for r in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if "ocr_results" not in existing_tables:
            return

        existing_columns = _table_columns(conn, "ocr_results")
        changed = False
        for col, sql_type in column_types.items():
            if col in existing_columns:
                continue
            conn.exec_driver_sql(f"ALTER TABLE ocr_results ADD COLUMN {col} {sql_type}")
            changed = True
        if changed:
            conn.commit()


def get_engine() -> Engine:
    if _ENGINE is None:
        raise RuntimeError("DB engine not initialized. Call init_db() first.")
    return _ENGINE


def get_session() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("DB not initialized. Call init_db() first.")
    return _SessionLocal()
