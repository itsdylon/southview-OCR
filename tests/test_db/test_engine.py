from __future__ import annotations

from southview.db.engine import get_engine, init_db


def test_init_db_sets_sqlite_busy_timeout(tmp_path):
    db_path = tmp_path / "busy-timeout.db"

    init_db(db_path)

    with get_engine().connect() as conn:
        busy_timeout = conn.exec_driver_sql("PRAGMA busy_timeout").scalar_one()

    assert busy_timeout == 5000
