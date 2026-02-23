# Subplan 1: Video Ingestion

## Goal
Accept iPhone video uploads, store them durably, and create database records to track them.

## Scope
- Video upload (API endpoint + CLI command)
- File storage in `data/videos/`
- Video metadata extraction (duration, resolution, fps, codec)
- Duplicate detection via SHA-256 hash
- Video record creation in database

## Implementation Details

### Upload Flow
1. Client sends video file via multipart upload or CLI points to local file path
2. Compute SHA-256 hash of the file
3. Check if a `Video` record with that hash already exists
   - If yes: return existing record (idempotent)
   - If no: continue
4. Extract metadata using OpenCV (`cv2.VideoCapture`)
5. Copy/move file to `data/videos/{video_id}.{ext}`
6. Create `Video` record in database
7. Optionally auto-create a `Job` record to start processing

### Video Metadata Extracted
- Duration (seconds)
- Resolution (width × height)
- FPS
- Codec
- File size
- Frame count

### Supported Formats
- MP4 (H.264, H.265/HEVC) — iPhone default
- MOV — iPhone alternative
- Any format OpenCV can read (fallback)

### File Naming
Videos stored as `{video_id}.{original_extension}` to preserve codec info.

### Key Functions
```
upload_video(file_path: str) -> Video
get_video(video_id: str) -> Video
list_videos() -> list[Video]
compute_file_hash(file_path: str) -> str
extract_video_metadata(file_path: str) -> dict
```

### Error Handling
- Corrupt/unreadable video → fail with clear error, no DB record created
- Insufficient disk space → check before copy, fail gracefully
- Duplicate upload → return existing record, no error

### API Endpoint
```
POST /api/videos/upload
  - Multipart file upload
  - Returns: Video record (JSON)

GET /api/videos
  - List all videos
  - Filterable by status

GET /api/videos/{id}
  - Video details including card count and job status
```

## Files to Create
- `src/southview/ingest/video_upload.py` — upload logic
- `src/southview/ingest/metadata.py` — metadata extraction
- Tests in `tests/test_ingest/`

## Dependencies
- OpenCV (`opencv-python-headless`)
- SQLAlchemy (for DB access)
- FastAPI (for API endpoint)
