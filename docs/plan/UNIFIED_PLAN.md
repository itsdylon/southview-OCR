# Southview OCR — Unified Architectural Plan

## 1. System Overview

A pipeline to digitize historical index cards from iPhone video into structured, searchable, confidence-scored text stored in a database with a manual review workflow.

```
┌─────────────┐    ┌─────────────────┐    ┌───────────────┐    ┌──────────┐
│ Video Upload │───▶│ Frame Extraction │───▶│ OCR + Scoring │───▶│ Database │
└─────────────┘    └─────────────────┘    └───────────────┘    └──────────┘
                                                                     │
                                                               ┌─────▼──────┐
                                                               │   Review    │
                                                               │  Workflow   │
                                                               └─────┬──────┘
                                                                     │
                                                               ┌─────▼──────┐
                                                               │   Export    │
                                                               │  & Backup  │
                                                               └────────────┘
```

## 2. Technology Choices

| Component         | Choice                  | Rationale                                         |
|-------------------|-------------------------|---------------------------------------------------|
| Language          | Python 3.11+            | Rich ML/CV ecosystem, fast prototyping             |
| Web framework     | FastAPI                 | Async, auto-docs, lightweight                      |
| Database          | SQLite (via SQLAlchemy) | Zero-config, file-portable, exportable, sufficient |
| OCR engine        | Tesseract (pytesseract) | Open-source, good typed-text accuracy              |
| Frame extraction  | OpenCV (cv2)            | Industry standard, handles iPhone H.264/HEVC       |
| Job queue         | SQLite-backed internal  | No Redis/RabbitMQ overhead for single-machine use  |
| GPU acceleration  | CUDA via OpenCV build   | RTX 3090 available for frame decode acceleration   |
| Frontend          | TBD (separate effort)   | `/frontend` folder reserved, mocked separately     |

### Why SQLite?

SQLite gives us:
- A single file database that can be copied/backed up trivially
- No server process to manage
- Easy export (the file IS the backup)
- Sufficient write throughput for our batch workload

**Multi-developer note:** Each developer runs their own local SQLite instance. The `data/` directory is gitignored — only the schema code (SQLAlchemy models) is shared via the repo. Every developer gets a fresh DB on first run via `init_db()`. There is no need for database consistency across developers since the data (videos, OCR results) is local and fully re-processable. For testing, each developer simply processes their own test videos. If we ever need a shared database or true concurrent writes, migrating to PostgreSQL via SQLAlchemy is straightforward.

## 3. Data Model (Core Entities)

```
Video
  ├── id (UUID)
  ├── filename
  ├── filepath (original video location)
  ├── upload_timestamp
  ├── status (uploaded | processing | completed | failed)
  └── metadata (duration, resolution, fps)

Job
  ├── id (UUID)
  ├── video_id (FK → Video)
  ├── job_type (frame_extraction | ocr | full_pipeline)
  ├── status (queued | running | completed | failed)
  ├── created_at
  ├── started_at
  ├── completed_at
  ├── error_message
  └── progress (0-100)

Card
  ├── id (UUID)
  ├── video_id (FK → Video)
  ├── job_id (FK → Job)
  ├── frame_number
  ├── image_path (extracted still image)
  ├── sequence_index (order within video)
  └── extracted_at

OCRResult
  ├── id (UUID)
  ├── card_id (FK → Card)
  ├── raw_text (full Tesseract output, preserved for audit)
  ├── raw_fields_json (JSON — original OCR-extracted field values before review)
  ├── confidence_score (0.0–1.0, card-level)
  ├── word_confidences (JSON — per-word confidence array)
  ├── ocr_engine_version
  ├── processed_at
  ├── review_status (pending | approved | flagged | corrected)
  ├── reviewed_by (nullable)
  ├── reviewed_at (nullable)
  │
  │── Structured Card Fields (current values — OCR-extracted, then corrected by reviewer)
  ├── deceased_name          (top of card, unlabeled — e.g., "AARON, Benjamin L.")
  ├── address                (top of card, unlabeled — e.g., "5566 Marbut Road, Lithonia, GA")
  ├── owner                  (lot/estate owner name)
  ├── relation               (owner's relation to deceased)
  ├── phone                  (Ph# — nullable, not always present)
  ├── date_of_death          (nullable — many cards missing this)
  ├── date_of_burial
  ├── description            (grave location: lot#, range, grave#, section, block, side)
  ├── sex
  ├── age
  ├── grave_type             (type of grave — e.g., "SVC Vault")
  ├── grave_fee              (e.g., "$675.00")
  ├── undertaker
  ├── board_of_health_no     (older cards)
  └── svc_no
```

## 4. Pipeline Stages

### Stage 1: Video Ingestion
- Accept video file upload (API endpoint or CLI)
- Store original video in `data/videos/`
- Create `Video` record in DB
- Create a `Job` record (type: `full_pipeline`)
- Trigger processing

### Stage 2: Frame Extraction
- Read video with OpenCV
- Detect distinct cards using scene-change / stability detection
- Extract one "best frame" per card (sharpest, most stable)
- Save frames as PNG to `data/frames/{video_id}/`
- Create `Card` records in DB
- Update job progress

### Stage 3: OCR Processing
- Load each card image
- Pre-process (deskew, contrast enhancement, noise reduction)
- Run Tesseract with confidence output (`--oem 1 --psm 6`)
- Extract word-level bounding boxes and confidences
- **Parse structured fields** by detecting known label positions ("Owner", "Date of death", etc.) and extracting associated text
- Handle unlabeled header: deceased name and address extracted from the top of the card by position
- Compute card-level confidence score (mean of word confidences)
- Store `OCRResult` records with both raw text and structured fields
- Preserve original OCR-extracted values in `raw_fields_json` for audit
- Flag cards below confidence threshold (default: 0.7) as `flagged`

### Stage 4: Review Workflow
- Frontend displays cards grouped by video/batch
- Flagged cards highlighted for priority review
- Reviewer sees: original card image alongside extracted structured fields (name, dates, description, etc.)
- Reviewer corrects individual fields; originals preserved in `raw_fields_json`
- Reviewer marks card as `approved` or `corrected`

### Stage 5: Export & Backup
- Export to CSV or JSON (all cards, or filtered by video/status)
- Automated database backup on configurable schedule
- Backup includes: SQLite file, frames directory listing

## 5. Job Lifecycle

```
                    ┌──────────┐
         upload ───▶│  QUEUED  │
                    └────┬─────┘
                         │ worker picks up
                    ┌────▼─────┐
                    │ RUNNING  │
                    └────┬─────┘
                   ┌─────┴──────┐
              success         failure
            ┌──▼───┐      ┌───▼───┐
            │ DONE │      │FAILED │
            └──────┘      └───┬───┘
                              │ retry
                         ┌────▼─────┐
                         │  QUEUED  │
                         └──────────┘
```

- Jobs are idempotent: re-running a job for a video deletes previous cards/results first, then reprocesses
- Job progress tracked as percentage (0–100)
- Failed jobs store error message for debugging

## 6. Confidence Scoring Strategy

| Level        | Source                              | Storage                     |
|-------------|--------------------------------------|-----------------------------|
| Word-level  | Tesseract word confidence (0–100)   | `word_confidences` JSON     |
| Card-level  | Mean of word confidences, normalized to 0.0–1.0 | `confidence_score` |

**Thresholds:**
- `>= 0.85` → auto-approved (high confidence)
- `0.70 – 0.84` → pending review
- `< 0.70` → flagged (priority review)

Thresholds are configurable in `config.yaml`.

## 7. File Storage Layout

```
data/
├── videos/              # Original uploaded videos
│   └── {video_id}.mp4
├── frames/              # Extracted card images
│   └── {video_id}/
│       ├── card_001.png
│       ├── card_002.png
│       └── ...
├── backups/             # Database backups
│   └── southview_2024-01-15_143022.db
└── exports/             # CSV/JSON exports
    └── export_2024-01-15.csv
```

## 8. API Endpoints (Planned)

| Method | Path                          | Description                    |
|--------|-------------------------------|--------------------------------|
| POST   | `/api/videos/upload`          | Upload a video file            |
| GET    | `/api/videos`                 | List all videos                |
| GET    | `/api/videos/{id}`            | Video details + card count     |
| POST   | `/api/jobs/{video_id}/start`  | Start processing a video       |
| GET    | `/api/jobs/{id}`              | Job status + progress          |
| GET    | `/api/cards`                  | List cards (filterable)        |
| GET    | `/api/cards/{id}`             | Card detail + OCR result       |
| PUT    | `/api/cards/{id}/review`      | Submit review (edit + approve) |
| GET    | `/api/export`                 | Export data (CSV/JSON)         |
| POST   | `/api/backup`                 | Trigger manual backup          |

## 9. Idempotency Strategy

- Each video gets a deterministic ID based on file hash (SHA-256)
- Re-uploading the same video returns the existing record
- Re-running a job deletes prior cards/OCR results for that video, then reprocesses
- This prevents duplicate cards while allowing reprocessing if OCR improves

## 10. Workstreams

The implementation is broken into 7 subplans (see `docs/plan/` for each):

1. **Video Ingestion** — Upload, storage, video record creation
2. **Frame Extraction** — Scene detection, best-frame selection, image output
3. **OCR Pipeline** — Pre-processing, Tesseract execution, confidence extraction
4. **Database Schema** — SQLAlchemy models, migrations, connection management
5. **Review Workflow** — API endpoints for review, status transitions
6. **Export & Backup** — CSV/JSON export, scheduled backups
7. **Job Lifecycle** — Queue management, progress tracking, retry logic

## 11. Development Order

```
Phase 1: Foundation
  ├── Database schema + models
  ├── Configuration system
  └── Project scaffold

Phase 2: Core Pipeline
  ├── Video ingestion (upload + storage)
  ├── Frame extraction
  └── OCR processing

Phase 3: Workflow
  ├── Job lifecycle management
  ├── Review workflow API
  └── Export & backup

Phase 4: Integration
  ├── End-to-end pipeline testing
  ├── CLI interface
  └── Frontend integration (when ready)
```
