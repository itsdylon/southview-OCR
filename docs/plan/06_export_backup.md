# Subplan 6: Export & Backup

## Goal
Ensure no progress is ever lost. Provide data export for external use and automated backups.

## Scope
- CSV and JSON export of card data
- Database file backup
- Backup scheduling
- Data integrity verification

## Export

### CSV Export
```
GET /api/export?format=csv&video_id=...&status=...
```
Columns:
- card_id
- video_filename
- sequence_index
- deceased_name
- address
- owner
- relation
- phone
- date_of_death
- date_of_burial
- description
- sex
- age
- grave_type
- grave_fee
- undertaker
- board_of_health_no
- svc_no
- confidence_score
- review_status
- reviewed_by
- image_path

### JSON Export
```
GET /api/export?format=json&video_id=...&status=...
```
Same fields as CSV, structured as JSON array. Optionally includes `raw_text` and `raw_fields_json` for audit purposes.

### Export Options
- Filter by video_id
- Filter by review_status
- Filter by confidence range
- Include/exclude word-level confidences
- Export all or filtered subset

## Backup Strategy

### What Gets Backed Up
1. **SQLite database file** (`data/southview.db`)
2. **Backup manifest** (list of videos and frame counts for integrity check)

### What Does NOT Need Backup
- Original videos (assumed preserved by the user separately)
- Frame images (re-extractable from videos)
- But we back up the DB which tracks everything

### Backup Mechanism
1. Use SQLite's `.backup` API (safe, consistent snapshot even during writes)
2. Save to `data/backups/southview_{timestamp}.db`
3. Keep last N backups (configurable, default 10)
4. Rotate out older backups

### Backup Triggers
- **Before processing**: Auto-backup before starting a new job
- **After review session**: Optional backup after batch of reviews
- **Manual**: `POST /api/backup` endpoint
- **CLI**: `python -m southview backup` command

### Backup Config
```yaml
backup:
  directory: data/backups
  max_backups: 10
  auto_backup_before_jobs: true
```

## Data Integrity

### Verification
- After backup: compare row counts between source and backup DB
- Periodic check: verify frame image files exist for all card records
- Export includes checksum in metadata

## Key Functions
```
export_csv(filters: ExportFilters, output_path: str) -> str
export_json(filters: ExportFilters, output_path: str) -> str
create_backup() -> str  # returns backup file path
list_backups() -> list[BackupInfo]
restore_backup(backup_path: str) -> None
rotate_backups(max_keep: int) -> None
verify_integrity() -> IntegrityReport
```

## Files to Create
- `src/southview/export/csv_export.py`
- `src/southview/export/json_export.py`
- `src/southview/backup/backup_manager.py`
- `src/southview/api/routes/export.py`
- `src/southview/api/routes/backup.py`
- Tests in `tests/test_export/` and `tests/test_backup/`

## Dependencies
- Standard library `csv`, `json`, `sqlite3` (for backup API)
- No additional dependencies
