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

    return _ENGINE


def get_engine() -> Engine:
    if _ENGINE is None:
        raise RuntimeError("DB engine not initialized. Call init_db() first.")
    return _ENGINE


def get_session() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("DB not initialized. Call init_db() first.")
    return _SessionLocal()