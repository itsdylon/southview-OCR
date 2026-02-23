"""Database engine and session management."""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from southview.config import get_config
from southview.db.models import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """Enable WAL mode and other performance pragmas for SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db(db_path: str | Path | None = None) -> Engine:
    """Initialize the database engine and create all tables."""
    global _engine, _SessionLocal

    if db_path is None:
        config = get_config()
        db_path = config["database"]["path"]

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    _engine = create_engine(f"sqlite:///{db_path}", echo=False)
    event.listen(_engine, "connect", _set_sqlite_pragmas)

    Base.metadata.create_all(_engine)

    _SessionLocal = sessionmaker(bind=_engine)
    return _engine


def get_session() -> Session:
    """Get a new database session."""
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()
