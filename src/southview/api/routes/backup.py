"""Backup management endpoints."""

from fastapi import APIRouter

from southview.backup.backup_manager import create_backup, list_backups

router = APIRouter(tags=["backup"])


@router.post("/backup")
def trigger_backup():
    """Create a manual database backup."""
    path = create_backup()
    return {"status": "success", "backup_path": path}


@router.get("/backups")
def get_backups():
    """List all available backups."""
    return list_backups()
