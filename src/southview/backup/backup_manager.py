"""SQLite database backup and rotation."""

import hashlib
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from southview.config import get_config


def _checksum_path(backup_path: str | Path) -> Path:
    return Path(backup_path).with_suffix(Path(backup_path).suffix + ".sha256")


def _compute_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_checksum(backup_path: str | Path) -> Path:
    checksum_path = _checksum_path(backup_path)
    checksum_path.write_text(f"{_compute_sha256(backup_path)}\n", encoding="utf-8")
    return checksum_path


def _verify_checksum(backup_path: str | Path) -> None:
    checksum_path = _checksum_path(backup_path)
    if not checksum_path.exists():
        raise ValueError(f"Backup checksum not found: {checksum_path}")

    expected = checksum_path.read_text(encoding="utf-8").strip().split()[0]
    actual = _compute_sha256(backup_path)
    if expected != actual:
        raise ValueError(f"Backup checksum mismatch for {backup_path}")


def _run_integrity_check(db_path: str | Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    finally:
        conn.close()

    result = row[0] if row else None
    if result != "ok":
        raise ValueError(f"SQLite integrity_check failed for {db_path}: {result}")


def create_backup() -> str:
    """
    Create a backup of the SQLite database using the SQLite backup API.

    Returns the path to the backup file.
    """
    config = get_config()
    db_path = Path(config["database"]["path"])
    backup_dir = Path(config["backup"]["directory"])
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"southview_{timestamp}.db"

    # Use SQLite backup API for a consistent snapshot
    source = sqlite3.connect(str(db_path))
    dest = sqlite3.connect(str(backup_path))
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()

    _run_integrity_check(backup_path)
    _write_checksum(backup_path)
    rotate_backups()
    return str(backup_path)


def list_backups() -> list[dict]:
    """List all available backups, newest first."""
    config = get_config()
    backup_dir = Path(config["backup"]["directory"])
    if not backup_dir.exists():
        return []

    backups = []
    for f in sorted(backup_dir.glob("southview_*.db"), reverse=True):
        backups.append({
            "filename": f.name,
            "path": str(f),
            "size_bytes": f.stat().st_size,
            "created": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
        })
    return backups


def rotate_backups() -> None:
    """Remove old backups beyond the configured max."""
    config = get_config()
    max_backups = config["backup"]["max_backups"]
    backup_dir = Path(config["backup"]["directory"])

    if not backup_dir.exists():
        return

    backups = sorted(backup_dir.glob("southview_*.db"), reverse=True)
    for old_backup in backups[max_backups:]:
        checksum_path = _checksum_path(old_backup)
        old_backup.unlink()
        checksum_path.unlink(missing_ok=True)


def restore_backup(backup_path: str | Path) -> None:
    """Restore a database backup by copying it to the active database path."""
    config = get_config()
    db_path = Path(config["database"]["path"])
    backup_path = Path(backup_path)
    temp_restore_path = db_path.with_name(f".{db_path.name}.restore")

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    _verify_checksum(backup_path)
    _run_integrity_check(backup_path)

    shutil.copy2(backup_path, temp_restore_path)
    try:
        _run_integrity_check(temp_restore_path)
        temp_restore_path.replace(db_path)
        _run_integrity_check(db_path)
    finally:
        temp_restore_path.unlink(missing_ok=True)
