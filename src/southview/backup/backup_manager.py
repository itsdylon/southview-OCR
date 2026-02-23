"""SQLite database backup and rotation."""

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from southview.config import get_config


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
        old_backup.unlink()


def restore_backup(backup_path: str | Path) -> None:
    """Restore a database backup by copying it to the active database path."""
    config = get_config()
    db_path = Path(config["database"]["path"])
    backup_path = Path(backup_path)

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    shutil.copy2(backup_path, db_path)
