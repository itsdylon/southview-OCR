"""Tests for backup management."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from southview.backup.backup_manager import (
    _checksum_path,
    create_backup,
    list_backups,
    restore_backup,
    rotate_backups,
)


def _config(tmp_path: Path, *, max_backups: int = 10) -> dict[str, object]:
    return {
        "database": {"path": str(tmp_path / "southview.db")},
        "backup": {
            "directory": str(tmp_path / "backups"),
            "max_backups": max_backups,
        },
    }


def _write_sample_db(db_path: Path, value: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS demo (value TEXT NOT NULL)")
        conn.execute("DELETE FROM demo")
        conn.execute("INSERT INTO demo (value) VALUES (?)", (value,))
        conn.commit()
    finally:
        conn.close()


def _read_sample_db(db_path: Path) -> str | None:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT value FROM demo").fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def test_create_backup_writes_checksum_and_lists_backup(tmp_path):
    config = _config(tmp_path)
    db_path = Path(config["database"]["path"])
    _write_sample_db(db_path, "original")

    with patch("southview.backup.backup_manager.get_config", return_value=config):
        backup_path = Path(create_backup())
        backups = list_backups()

    assert backup_path.exists()
    assert _checksum_path(backup_path).exists()
    assert len(backups) == 1
    assert backups[0]["path"] == str(backup_path)


def test_rotate_backups_removes_old_backup_checksums(tmp_path):
    config = _config(tmp_path, max_backups=2)
    backup_dir = Path(config["backup"]["directory"])
    backup_dir.mkdir(parents=True, exist_ok=True)

    for name in (
        "southview_20260412_030000.db",
        "southview_20260412_020000.db",
        "southview_20260412_010000.db",
    ):
        backup_path = backup_dir / name
        backup_path.write_bytes(b"backup")
        _checksum_path(backup_path).write_text("checksum\n", encoding="utf-8")

    with patch("southview.backup.backup_manager.get_config", return_value=config):
        rotate_backups()

    assert (backup_dir / "southview_20260412_030000.db").exists()
    assert (backup_dir / "southview_20260412_020000.db").exists()
    assert not (backup_dir / "southview_20260412_010000.db").exists()
    assert not (backup_dir / "southview_20260412_010000.db.sha256").exists()


def test_restore_backup_verifies_checksum_and_restores_database(tmp_path):
    config = _config(tmp_path)
    db_path = Path(config["database"]["path"])
    _write_sample_db(db_path, "before-backup")

    with patch("southview.backup.backup_manager.get_config", return_value=config):
        backup_path = Path(create_backup())

    _write_sample_db(db_path, "after-backup")
    assert _read_sample_db(db_path) == "after-backup"

    with patch("southview.backup.backup_manager.get_config", return_value=config):
        restore_backup(backup_path)

    assert _read_sample_db(db_path) == "before-backup"


def test_restore_backup_rejects_tampered_checksum(tmp_path):
    config = _config(tmp_path)
    db_path = Path(config["database"]["path"])
    _write_sample_db(db_path, "original")

    with patch("southview.backup.backup_manager.get_config", return_value=config):
        backup_path = Path(create_backup())

    _checksum_path(backup_path).write_text("not-the-real-checksum\n", encoding="utf-8")

    with patch("southview.backup.backup_manager.get_config", return_value=config):
        with pytest.raises(ValueError, match="checksum mismatch"):
            restore_backup(backup_path)
