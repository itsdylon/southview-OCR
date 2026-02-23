# Subplan 4: Database Schema

## Goal
Define and implement the SQLite database via SQLAlchemy ORM with all tables needed for the pipeline.

## Scope
- SQLAlchemy model definitions
- Database initialization and connection management
- Migration strategy
- Query helpers

## Schema

### videos
| Column           | Type        | Constraints       | Notes                          |
|------------------|-------------|-------------------|--------------------------------|
| id               | VARCHAR(36) | PK                | UUID                           |
| filename         | VARCHAR     | NOT NULL          | Original filename              |
| filepath         | VARCHAR     | NOT NULL          | Path to stored video           |
| file_hash        | VARCHAR(64) | UNIQUE, NOT NULL  | SHA-256 for dedup              |
| status           | VARCHAR(20) | NOT NULL          | uploaded/processing/completed/failed |
| duration_seconds | FLOAT       | nullable          |                                |
| resolution_w     | INTEGER     | nullable          |                                |
| resolution_h     | INTEGER     | nullable          |                                |
| fps              | FLOAT       | nullable          |                                |
| frame_count      | INTEGER     | nullable          |                                |
| file_size_bytes  | INTEGER     | nullable          |                                |
| upload_timestamp | DATETIME    | NOT NULL          | Default: now                   |
| metadata_json    | TEXT        | nullable          | Extra metadata as JSON         |

### jobs
| Column         | Type        | Constraints      | Notes                          |
|----------------|-------------|------------------|--------------------------------|
| id             | VARCHAR(36) | PK               | UUID                           |
| video_id       | VARCHAR(36) | FK → videos.id   |                                |
| job_type       | VARCHAR(30) | NOT NULL         | frame_extraction/ocr/full_pipeline |
| status         | VARCHAR(20) | NOT NULL         | queued/running/completed/failed |
| progress       | INTEGER     | DEFAULT 0        | 0–100                          |
| error_message  | TEXT        | nullable         |                                |
| created_at     | DATETIME    | NOT NULL         |                                |
| started_at     | DATETIME    | nullable         |                                |
| completed_at   | DATETIME    | nullable         |                                |

### cards
| Column         | Type        | Constraints      | Notes                          |
|----------------|-------------|------------------|--------------------------------|
| id             | VARCHAR(36) | PK               | UUID                           |
| video_id       | VARCHAR(36) | FK → videos.id   |                                |
| job_id         | VARCHAR(36) | FK → jobs.id     |                                |
| frame_number   | INTEGER     | NOT NULL         | Frame index in source video    |
| image_path     | VARCHAR     | NOT NULL         | Path to extracted PNG          |
| sequence_index | INTEGER     | NOT NULL         | Order within video (1, 2, 3…)  |
| extracted_at   | DATETIME    | NOT NULL         |                                |

**Unique constraint**: (video_id, sequence_index) — prevents duplicate cards per video.

### ocr_results
| Column             | Type        | Constraints      | Notes                         |
|--------------------|-------------|------------------|-------------------------------|
| id                 | VARCHAR(36) | PK               | UUID                          |
| card_id            | VARCHAR(36) | FK → cards.id, UNIQUE |                          |
| raw_text           | TEXT        | NOT NULL         | Original Tesseract output     |
| corrected_text     | TEXT        | nullable         | Reviewer-edited text          |
| confidence_score   | FLOAT       | NOT NULL         | 0.0–1.0                      |
| word_confidences   | TEXT        | nullable         | JSON array                    |
| ocr_engine_version | VARCHAR     | nullable         | e.g., "tesseract-5.3.0"      |
| processed_at       | DATETIME    | NOT NULL         |                               |
| review_status      | VARCHAR(20) | NOT NULL         | pending/approved/flagged/corrected |
| reviewed_by        | VARCHAR     | nullable         |                               |
| reviewed_at        | DATETIME    | nullable         |                               |

## Indexes
- `videos.file_hash` — fast duplicate lookup
- `jobs.video_id` — find jobs for a video
- `jobs.status` — find queued/running jobs
- `cards.video_id` — find cards for a video
- `ocr_results.card_id` — one-to-one lookup
- `ocr_results.review_status` — filter by review status
- `ocr_results.confidence_score` — sort/filter by confidence

## Connection Management
- Single SQLite file at `data/southview.db`
- SQLAlchemy session factory with scoped sessions
- Context manager for request-scoped sessions in API
- WAL mode enabled for better concurrent read performance

## Migration Strategy
For this project phase, we use `create_all()` to initialize the schema. If the schema evolves significantly, we'll add Alembic. For now:
- `init_db()` creates all tables if they don't exist
- Schema changes during development: drop and recreate (data is re-processable)
- Production data safety: export before schema changes

## Key Functions
```
init_db(db_path: str) -> Engine
get_session() -> Session
```

## Files to Create
- `src/southview/db/models.py` — SQLAlchemy models
- `src/southview/db/engine.py` — engine/session management
- `src/southview/db/__init__.py` — exports

## Dependencies
- SQLAlchemy >= 2.0
