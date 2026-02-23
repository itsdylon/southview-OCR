# Subplan 7: Job Lifecycle Management

## Goal
Manage processing jobs from creation through completion with progress tracking, error handling, and retry capability.

## Scope
- Job creation and queuing
- Job execution orchestration
- Progress tracking
- Error handling and retry
- Idempotency enforcement

## Job Types

| Type               | Description                                   |
|--------------------|-----------------------------------------------|
| `frame_extraction` | Extract frames from video only                |
| `ocr`             | Run OCR on already-extracted frames           |
| `full_pipeline`   | Frame extraction → OCR (the normal flow)      |

## Job State Machine

```
  create_job()
      │
      ▼
  ┌────────┐
  │ QUEUED │
  └───┬────┘
      │ start_job()
      ▼
  ┌─────────┐
  │ RUNNING │ ◄── progress updates (0–100%)
  └───┬─────┘
      │
  ┌───┴────┐
  │        │
  ▼        ▼
┌──────┐ ┌────────┐
│ DONE │ │ FAILED │
└──────┘ └───┬────┘
             │ retry_job()
             ▼
         ┌────────┐
         │ QUEUED │
         └────────┘
```

## Job Execution Flow (full_pipeline)

```python
def run_full_pipeline(job_id, video_id):
    job = get_job(job_id)
    video = get_video(video_id)

    try:
        mark_running(job)

        # Phase 1: Frame extraction (0–50% progress)
        cleanup_previous_cards(video_id)  # idempotency
        cards = extract_frames(video)
        update_progress(job, 50)

        # Phase 2: OCR (50–100% progress)
        for i, card in enumerate(cards):
            process_card_ocr(card)
            progress = 50 + int((i + 1) / len(cards) * 50)
            update_progress(job, progress)

        mark_completed(job)
        update_video_status(video, "completed")

    except Exception as e:
        mark_failed(job, str(e))
        update_video_status(video, "failed")
        raise
```

## Idempotency

When a job is re-run for a video:
1. Delete all existing `OCRResult` records for cards of this video
2. Delete all existing `Card` records for this video
3. Delete frame image files from `data/frames/{video_id}/`
4. Re-extract and re-process from scratch
5. This ensures clean results without duplicates

The video record itself is never deleted (preserves upload history).

## Progress Tracking

- Stored as integer 0–100 on the `Job` record
- Updated after each meaningful step
- For `full_pipeline`:
  - 0–50%: frame extraction progress
  - 50–100%: OCR progress (per-card increments)
- Queryable via `GET /api/jobs/{id}`

## Error Handling

### Per-Card Errors
- If OCR fails on a single card, log the error and continue
- The card gets an OCR result with confidence 0.0 and review_status "flagged"
- The job continues processing remaining cards

### Job-Level Errors
- If frame extraction fails entirely → job marked as failed
- If a critical error occurs → job marked as failed with error message
- Failed jobs can be retried via `POST /api/jobs/{id}/retry`

### Retry Logic
- Retry creates a new job (preserves history of the failed attempt)
- The new job re-runs the full pipeline (idempotent cleanup first)
- No automatic retry — manual trigger only (prevents infinite loops)

## Concurrency

- Single-worker model: one job runs at a time
- Jobs are processed in FIFO order from the queue
- This is sufficient for single-machine, single-user operation
- If needed later: add a simple worker pool

## API Endpoints

```
POST /api/jobs/{video_id}/start
  - Creates and starts a full_pipeline job
  - Returns: Job record

GET /api/jobs/{id}
  - Returns: Job record with progress

GET /api/jobs
  - List all jobs, filterable by status

POST /api/jobs/{id}/retry
  - Retry a failed job
  - Returns: New Job record
```

## Key Functions
```
create_job(video_id: str, job_type: str) -> Job
start_job(job_id: str) -> None
update_progress(job_id: str, progress: int) -> None
mark_completed(job_id: str) -> None
mark_failed(job_id: str, error: str) -> None
retry_job(job_id: str) -> Job
cleanup_previous_results(video_id: str) -> None
```

## Files to Create
- `src/southview/jobs/manager.py` — job lifecycle management
- `src/southview/jobs/runner.py` — job execution orchestrator
- `src/southview/jobs/cleanup.py` — idempotency cleanup
- `src/southview/api/routes/jobs.py` — API endpoints
- Tests in `tests/test_jobs/`
