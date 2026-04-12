# Southview OCR — Production Hardening Audit

**Date:** 2026-04-11
**Branch:** `codex/bake-off` (commit `94c8424`)
**Scope:** Full-stack audit of FastAPI backend, React frontend, SQLite data layer, job pipeline, OCR integration, and deployment posture.

---

## How to use this document

Each issue has a severity tag (P0 critical through P3 low), the file path and line numbers where the problem lives, a description of the risk, and a concrete remediation. Issues are grouped by category and ordered by severity within each group. Items marked with an asterisk (*) were already identified before this audit and are included for completeness.

---

## 1. Security

### 1.1 P0 — Path traversal on upload filename *

**File:** `src/southview/api/routes/videos.py:90-91`
**Status:** Closed on 2026-04-11. Confirmed as a real concern even for an internal VPS deployment because any authenticated session could write outside the temp upload directory. The upload route now strips both POSIX and Windows-style path components before constructing the temp path, and regression coverage was added.

The user-supplied `file.filename` is joined directly into the temp directory path. A crafted filename like `../../etc/cron.d/evil` would write outside the temp dir.

**Remediation:** Strip the filename to its basename and reject names containing path separators:

```python
import re, uuid
safe_name = re.sub(r'[^\w.\-]', '_', Path(file.filename or "upload.mp4").name)
# Or simply: safe_name = f"{uuid.uuid4()}{suffix}"
```

### 1.2 P0 — Path traversal on video_id in blur-queue endpoint

**File:** `src/southview/api/routes/videos.py:179-180`
**Status:** Closed on 2026-04-11. The originally documented `../../../etc/passwd` exploit path was overstated because FastAPI route matching does not pass multi-segment values through this parameter. There was still an avoidable filesystem trust issue for reachable single-segment values such as `..`, so the endpoint now requires a real video row first and only builds filesystem paths from the canonical database ID.

`video_id` is used directly in path construction (`frames_root / video_id`). An attacker can pass `../../../etc/passwd` as the video_id to read arbitrary files from disk via the returned `image_path` values.

**Remediation:** Validate that `video_id` matches the UUID format (`^[0-9a-f\-]{36}$`) or look up the video by ID in the database first and reject unknown IDs before any filesystem access.

### 1.3 P0 — Path traversal in SPA fallback catch-all

**File:** `src/southview/api/app.py:73-79`
**Status:** Closed on 2026-04-11. Confirmed as a real concern because the catch-all route accepts multi-segment paths and previously trusted them as relative filesystem paths. The fallback now resolves requested files against `frontend/dist` and serves `index.html` whenever the resolved path escapes that directory; regression coverage was added.

The `spa_fallback` route serves any file under `_FRONTEND_DIR / path` where `path` comes from the URL. A request to `/%2e%2e/%2e%2e/etc/passwd` (URL-encoded `../../etc/passwd`) could serve arbitrary files.

**Remediation:** Resolve the path and verify it stays within the frontend directory:

```python
resolved = (_FRONTEND_DIR / path).resolve()
if not str(resolved).startswith(str(_FRONTEND_DIR.resolve())):
    return FileResponse(_FRONTEND_DIR / "index.html")
```

### 1.4 P0 — Timing attack on username comparison

**File:** `src/southview/auth.py:56`
**Status:** Closed on 2026-04-11. Real but lower practical impact for this internal deployment: login is still internet-reachable on the VPS, and the fixed admin username made enumeration especially cheap. `verify_login()` now uses a constant-time username comparison and always performs a password verification pass before returning.

`username != settings.username` is a standard string comparison that leaks timing information about the valid username. Combined with the hardcoded default `"admin"`, this makes enumeration trivial.

**Remediation:** Use `hmac.compare_digest()` for the username check, or always proceed to the password check regardless of username match (returning `False` at the end if the username was wrong).

### 1.5 P1 — Insecure cookie defaults (`secure=False`)

**File:** `src/southview/auth.py:37`
**Status:** Closed on 2026-04-11. Real concern for the Hetzner VPS deployment because the app is intended to sit behind HTTPS and cookie transport security should be the safe default. Secure cookies now default to `True` outside `SOUTHVIEW_ENV=development`, and the local setup docs/tests were updated to opt out explicitly during HTTP development.

`secure_cookies` defaults to `False`. In production over HTTPS, session cookies are still sent over HTTP redirects or mixed content, enabling MITM session hijacking.

**Remediation:** Default `secure_cookies` to `True`. Only allow `False` when an explicit `SOUTHVIEW_ENV=development` flag is set.

### 1.6 P1 — CORS allows all methods and headers with credentials

**File:** `src/southview/api/app.py:29-35`
**Status:** Closed on 2026-04-11. Low immediate risk in the current repo state because CORS was still limited to localhost origins, but it would have become unsafe the moment a production origin was added. The CORS policy now allows only explicit methods and the `Content-Type` header.

`allow_methods=["*"]` and `allow_headers=["*"]` combined with `allow_credentials=True` is overly permissive. While origins are currently locked to localhost, any future origin addition inherits this broad access.

**Remediation:** Restrict to specific methods (`["GET", "POST", "PUT", "DELETE"]`) and specific headers (`["Content-Type"]`). Make `allow_origins` configurable via environment variable for deployment flexibility.

### 1.7 P1 — Hardcoded CORS origins (localhost only)

**File:** `src/southview/api/app.py:31`
**Status:** Closed on 2026-04-11. Real deployment concern: a production frontend would have required a code change or a same-origin reverse-proxy setup. Allowed origins are now configurable through `SOUTHVIEW_CORS_ORIGINS`, while localhost remains the development default.

Origins are hardcoded to `localhost:5173`. Production deployment will require code changes.

**Remediation:** Read allowed origins from an env var (e.g., `SOUTHVIEW_CORS_ORIGINS`), falling back to localhost for development.

### 1.8 P1 — No CSRF protection on state-mutating endpoints

**Files:** All POST/PUT/DELETE routes; `frontend/src/app/data/api.ts:28-48`
**Status:** Closed on 2026-04-11 with no additional code changes. For this internal single-admin deployment, the combination of `SameSite=strict` session cookies and the now-explicit CORS allowlist materially reduces browser-driven CSRF exposure. I am not layering in a second CSRF mechanism yet; instead I added regression coverage to preserve the strict cookie behavior this assessment depends on.

Cookie-based auth without CSRF tokens means any cross-origin page (if CORS is misconfigured or via subdomain takeover) can make authenticated requests.

**Remediation:** Implement double-submit cookie CSRF protection or add a custom header check (e.g., `X-Requested-With`) that the frontend always sends and the backend validates.

### 1.9 P1 — No rate limiting on login endpoint

**File:** `src/southview/api/routes/auth.py:35-52`
**Status:** Closed on 2026-04-11. Real concern even for an internal VPS deployment because the login endpoint is still network-exposed and there is only one admin account to protect. The route now applies a lightweight in-memory per-client throttle suited to the current single-instance topology: 5 failed attempts within 60 seconds triggers a 15-minute lockout.

The login endpoint has no rate limiting or account lockout. With a single admin account and potentially weak password, brute-force attacks are straightforward.

**Remediation:** Add rate limiting (e.g., `slowapi` library) with exponential backoff after failed attempts. Consider IP-based throttling: 5 attempts per minute, 15-minute lockout.

### 1.10 P1 — No rate limiting or size limit on upload endpoint *

**File:** `src/southview/api/routes/videos.py:78-112`
**Status:** Closed on 2026-04-12. Real concern even for an internal VPS deployment because accidental oversized uploads are plausible and concurrent multi-gigabyte uploads can still exhaust disk or tie up the service. The upload route now enforces a configurable byte limit while streaming and applies a lightweight in-memory per-client concurrent upload cap that matches the current single-instance architecture.

No app-level max file size, no rate limit per IP/session, no concurrent upload limit. An attacker can fill disk with large files or starve workers with many simultaneous uploads.

**Remediation:** Add `UploadFile` size validation, configure a max request body size, and add rate limiting. Example:

```python
MAX_UPLOAD_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB
if file.size and file.size > MAX_UPLOAD_BYTES:
    raise HTTPException(413, "File too large")
```

### 1.11 P1 — Config file tampering via regex injection

**File:** `src/southview/api/routes/settings.py:39-48`
**Status:** Closed on 2026-04-12. The original “regex injection” framing was somewhat overstated because FastAPI/Pydantic already coerced the payload to numeric values, but the persistence mechanism was still brittle. The endpoint now validates thresholds as finite `0.0`–`1.0` numbers and persists them through YAML load/modify/write instead of regex substitution.

User-supplied threshold values are interpolated into `re.sub()` replacement strings. Special regex characters or newlines could corrupt the config file.

**Remediation:** Use a proper YAML library (`yaml.safe_dump`) to read-modify-write the config file, or validate that values are within expected numeric ranges before string substitution.

### 1.12 P2 — Error information leakage across multiple routes

**Files:** `videos.py:110,260`, `cards.py:171,228,269`, `export.py:51`

`detail=str(e)` in HTTP exception handlers exposes internal paths, library internals, and database schema details to API consumers.

**Remediation:** Log the full exception server-side at ERROR level. Return a generic message to the client with a correlation ID for debugging:

```python
import uuid
error_id = uuid.uuid4().hex[:8]
logger.exception("Request failed [%s]", error_id)
raise HTTPException(500, detail=f"Internal error (ref: {error_id})")
```

### 1.13 P2 — Missing input validation on query parameters

**Files:** `videos.py:116` (status filter), `cards.py:132-147`

`status` parameters are accepted as free-form strings. Invalid values may cause unexpected query behavior or ORM errors.

**Remediation:** Use `Literal` types or Enums:

```python
from typing import Literal
def list_videos(status: Literal["uploaded", "processing", "completed", "failed"] | None = None):
```

### 1.14 P2 — No content-type / magic-byte validation on uploads

**File:** `src/southview/api/routes/videos.py:81-87`

Only file extension is checked. A ZIP or executable renamed to `.mp4` passes validation and wastes pipeline resources before failing at frame extraction.

**Remediation:** Read the first few bytes of the file and validate against expected magic bytes for video formats, or use `python-magic` for MIME detection.

---

## 2. Reliability & Error Handling

### 2.1 P0 — Race condition: duplicate job starts for same video

**Files:** `src/southview/api/routes/jobs.py:30-53`, `src/southview/jobs/runner.py:27-29`
**Status:** Closed on 2026-04-12. Real concern even on the single-server Hetzner deployment because two quick requests from the UI could still race within the same process and start overlapping workers against the same video. Job creation is now serialized per video in-process, active jobs are deduplicated at the manager layer, and the routes return the existing active job instead of spawning another thread.

Nothing prevents two concurrent `POST /api/jobs/{video_id}/start` requests from creating two jobs and spawning two threads processing the same video simultaneously. Both threads will call `cleanup_previous_results`, causing data corruption.

**Remediation:** Add a database-level guard: either a unique partial index on `(video_id, status)` where status is `queued` or `running`, or use `SELECT ... FOR UPDATE` semantics (not available in SQLite — consider an application-level lock or mutex per video_id).

### 2.2 P0 — Destructive cleanup with no backup before reprocessing

**File:** `src/southview/jobs/cleanup.py:11-36`
**Status:** Closed on 2026-04-12. Real concern for this deployment because reprocessing is an operator-driven action and the old implementation could wipe the only known-good results before the new run proved itself. Reprocessing now creates a pre-job database backup when prior results exist, and old frame files are stashed and automatically restored if the new pipeline fails before completion.

`cleanup_previous_results()` permanently deletes all cards, OCR results, and frame images for a video. If the subsequent pipeline run fails mid-way, all previous work is irrecoverably lost.

**Remediation:** Either soft-delete previous results (flag as superseded) or create a checkpoint/snapshot before cleanup. At minimum, defer cleanup of frame files until new extraction succeeds.

### 2.3 P0 — No retry logic for Gemini API calls

**File:** `src/southview/ocr/gemini_wrapper.py:184-213`
**Status:** Closed on 2026-04-12. Real concern because the VPS deployment depends on a remote API where transient 429s and network hiccups are normal operational conditions, not exceptional edge cases. Gemini requests now retry with exponential backoff and optional jitter on HTTP 429/5xx and network errors, while still failing fast on invalid API keys.

External HTTP calls to the Gemini API have no retry mechanism. A single transient network failure or rate-limit response kills the entire OCR batch.

**Remediation:** Implement exponential backoff with jitter, retrying on HTTP 429 (rate limit) and 5xx errors, with a configurable max retry count (e.g., 3-5 attempts).

### 2.4 P1 — Upload handler blocks the async event loop *

**File:** `src/southview/api/routes/videos.py:79,94`, `src/southview/ingest/video_upload.py:76`
**Status:** Closed on 2026-04-12. Real concern because large uploads are expected in normal use, and the previous `async` route performed synchronous disk I/O on the event loop thread. The upload endpoint is now synchronous so FastAPI runs it in the threadpool, which is a better fit for this blocking work on the current single-node deployment.

The `async` upload endpoint performs synchronous file I/O (`shutil.copyfileobj`), hashing, and metadata extraction on the event loop thread. Large uploads starve all other request handling.

**Remediation:** Either make the endpoint synchronous (remove `async`) so FastAPI runs it in a threadpool, or explicitly use `await run_in_executor(...)` for the blocking operations.

### 2.5 P1 — Daemon threads are not durable across restarts *

**File:** `src/southview/api/routes/jobs.py:49-53`
**Status:** Closed on 2026-04-12. Real concern because this deployment still runs in-process daemon threads, so a restart or crash can strand jobs and videos in misleading in-progress states. App startup now sweeps any `running` jobs into `failed` with a restart message and marks corresponding videos as failed, which gives operators a clean recovery path until a real task queue is introduced.

Background processing uses `daemon=True` threads. Server restart or crash kills in-flight jobs with no recovery mechanism. Jobs remain in `running` status forever (zombie jobs).

**Remediation:** For immediate improvement: add a startup sweep that marks any `running` jobs as `failed` with a "server restarted" message. For production: migrate to a task queue (Celery, RQ, or arq) with persistent job state and automatic retries.

### 2.6 P1 — OCR batch aborts entirely on provider error

**File:** `src/southview/ocr/batch.py:243-267`
**Status:** Closed on 2026-04-12. Real concern because transient provider outages should degrade throughput, not wipe out the entire batch. Provider errors are now handled per card: the batch keeps going, failed cards are flagged instead of aborting the run, and Gemini provider failures can fall back to Tesseract via the configured fallback engine.

When `OCRProviderError` is raised (e.g., API key invalid, quota exceeded), the entire batch is aborted. There is no fallback to Tesseract or partial-success handling.

**Remediation:** Implement per-card error handling: catch provider errors per card, mark individual cards as failed, continue processing remaining cards. Add fallback to Tesseract OCR when Gemini is unavailable.

### 2.7 P1 — Exception re-raised from background thread

**File:** `src/southview/jobs/runner.py:148-164`
**Status:** Closed on 2026-04-12 with no code change to `run_full_pipeline()`. After review, this concern was overstated for the current architecture: all API-started pipeline threads already run through `_run_job_safely()`, which catches and contains the re-raised exception after the job has been marked failed. I kept the `raise` in place because the CLI `process` command calls `run_full_pipeline()` directly and should still surface failures to the operator; regression coverage now locks in the thread-wrapper behavior this decision depends on.

After marking the job as failed, the exception is re-raised (`raise` on line 164). This causes the daemon thread to terminate with an unhandled exception. While `_run_job_safely` in `jobs.py:22-27` catches it, the pattern is fragile.

**Remediation:** Remove the `raise` on line 164 (the job is already marked failed and the error logged), or ensure the thread wrapper always catches and logs.

### 2.8 P2 — All upload exceptions become HTTP 400 *

**File:** `src/southview/api/routes/videos.py:109-110`
**Status:** Closed on 2026-04-12. Real concern because it hid infrastructure problems behind client-looking errors, which would have made monitoring and operator diagnosis much harder on the VPS. The upload route now preserves explicit HTTP errors, maps validation failures to `400`, missing files to `404`, and storage/unknown failures to `500`.

The catch-all `except Exception as e: raise HTTPException(status_code=400, ...)` masks genuine server errors (disk full, DB down, permission denied) as client errors, making diagnosis and monitoring impossible.

**Remediation:** Differentiate error types: `ValueError`/validation errors return 400, `FileNotFoundError` returns 404, `OSError`/`IOError` returns 500 (disk issues), and unknown exceptions return 500.

### 2.9 P2 — Double disk write during upload ingest *

**File:** `src/southview/api/routes/videos.py:89-95`, `src/southview/ingest/video_upload.py:127`
**Status:** Closed on 2026-04-12. Real concern for this workload because the application handles large video files, so copying a fully written upload a second time wastes both time and disk I/O. Uploads are now staged directly inside the videos storage directory and the ingest service renames that staged file into place when persisting a new video or restoring a missing deduped source.

The file is first written to a temp directory, then copied to final storage. For multi-gigabyte videos this doubles write time and disk pressure.

**Remediation:** Write directly to the final storage location using a temporary name, then atomically rename on success. Or stream to final path and compute hash in a single pass.

### 2.10 P2 — Temp directory leak on crash

**File:** `src/southview/api/routes/videos.py:89-112`
**Status:** Closed on 2026-04-12. Real concern, although lower impact on a single internal VPS than on a multi-tenant system: after the `2.9` staging change, the failure mode became stale `.upload-*` files in `videos_dir` rather than leaked temp directories, but a hard kill during a large upload could still strand significant disk usage. The app now sweeps stale staged-upload files on startup using a configurable age threshold, which is a good fit for this service’s restart-driven deployment model without adding a background janitor.

`tempfile.mkdtemp()` is used with a manual `finally` cleanup. If the process is killed (SIGKILL, OOM) between creation and cleanup, the temp directory is orphaned permanently.

**Remediation:** Use `tempfile.TemporaryDirectory()` context manager. Additionally, add a periodic cleanup job that removes stale temp directories older than a threshold.

### 2.11 P2 — Settings read-modify-write race condition

**File:** `src/southview/api/routes/settings.py:38-49`
**Status:** Closed on 2026-04-12. Real but low-frequency concern for the current deployment because there is usually one operator, but concurrent threshold saves could still overwrite each other. The settings write path now takes an exclusive file lock around the YAML read-modify-write sequence.

The settings endpoint reads the config file, modifies it with regex, and writes it back without any file locking. Concurrent requests can overwrite each other's changes.

**Remediation:** Use file locking (`fcntl.flock` on Unix) around the read-modify-write cycle, or move configuration to the database.

### 2.12 P2 — No idempotency in frame extraction

**File:** `src/southview/extraction/frame_extractor.py:44-47`
**Status:** Closed on 2026-04-12. Real concern, but partially reduced by the earlier reprocessing snapshot work: the main pipeline would already restore old frame output on failure, yet the extractor itself still deleted prior manifests/decisions before new extraction finished. Frame extraction now writes into a sibling staging directory and swaps the completed result into place only after success, so previous frame output stays intact until a fresh extraction is complete.

Previous extraction decisions are deleted at the start of extraction. If extraction is interrupted, previous decisions are lost and re-running produces potentially different frame selections.

**Remediation:** Write new extraction results to a temporary location, then atomically swap with the old results on success.

### 2.13 P2 — No timeout on video metadata extraction

**File:** `src/southview/ingest/metadata.py:17-45`

`cv2.VideoCapture.get()` can hang indefinitely on corrupted or network-mounted files.

**Remediation:** Wrap metadata extraction in a timeout (e.g., `signal.alarm` on Unix or a subprocess with timeout).

### 2.14 P2 — Incomplete export with silent file skipping

**File:** `src/southview/export/service.py:24-79`

If a card's image file is missing during export, `FileNotFoundError` is silently caught and the file is skipped. The user receives an incomplete ZIP with no warning.

**Remediation:** Track skipped files and include a manifest or warning in the ZIP. Alternatively, pre-validate all file references before starting the export.

---

## 3. Data Integrity

### 3.1 P1 — SQLite concurrency limitations under load

**File:** `src/southview/db/engine.py:26-31`

SQLite with WAL mode and `check_same_thread=False` supports concurrent reads but only one writer at a time. Under moderate concurrent write load (multiple uploads + job processing + review submissions), `SQLITE_BUSY` errors will occur.

**Remediation:** For immediate mitigation: set `PRAGMA busy_timeout=5000` to retry busy locks. For production scale: document concurrency limits or migrate to PostgreSQL.

### 3.2 P1 — Inline migrations without version tracking

**File:** `src/southview/db/engine.py:47-136`

Migrations run on every startup via custom functions with no version tracking. The `_migrate_filepath_nullable` migration recreates the videos table, which drops all indexes, triggers, and foreign key references. There is no rollback mechanism.

**Remediation:** Adopt Alembic for schema migrations with version tracking, rollback support, and idempotent execution.

### 3.3 P2 — Missing database indexes on frequently queried columns

**File:** `src/southview/db/models.py`

`Job.status` and `Card.video_id` are frequently filtered in queries but lack explicit indexes. As data grows, list queries will degrade.

**Remediation:** Add indexes:

```python
class Job(Base):
    __table_args__ = (Index("ix_jobs_status", "status"),)

class Card(Base):
    __table_args__ = (Index("ix_cards_video_id", "video_id"),)
```

### 3.4 P2 — No optimistic locking on review submissions

**File:** `src/southview/review/service.py:161-224`

Two reviewers can submit edits for the same card simultaneously. The last write wins with no conflict detection.

**Remediation:** Add a `version` or `updated_at` column to `OCRResult`. On submit, verify the version matches and return 409 Conflict if it has been modified.

### 3.5 P2 — N+1 query in card listing

**File:** `src/southview/review/service.py:142-149`

Card queries eagerly load `OCRResult` but not the `Video` relationship. If the API later accesses `card.video`, it triggers a lazy-load query per card.

**Remediation:** Add `.options(joinedload(Card.video))` to card listing queries.

### 3.6 P2 — No job deduplication guard

**File:** `src/southview/jobs/manager.py:9-22`

`create_job` does not check for existing active jobs for the same video. Double-clicking the "Start Job" button creates duplicate concurrent jobs.

**Remediation:** Before creating a new job, check for existing `queued` or `running` jobs for the same `video_id` and return the existing job instead.

### 3.7 P3 — Backup restore lacks integrity verification

**File:** `src/southview/backup/backup_manager.py:70-79`

`restore_backup()` uses `shutil.copy2()` without verifying the backup file's integrity. A corrupted backup silently overwrites the live database.

**Remediation:** Compute and store a checksum when creating backups. Verify the checksum before restoring. Run `PRAGMA integrity_check` after restore.

---

## 4. Frontend

### 4.1 P1 — No global React error boundary

**File:** `frontend/src/app/App.tsx`

The app has no error boundary component. A rendering error in any component crashes the entire application with a blank screen.

**Remediation:** Wrap the root component in a React error boundary that shows a fallback UI with a "reload" button.

### 4.2 P1 — No client-side upload size validation

**File:** `frontend/src/app/components/upload-video-dialog.tsx:48-55`

File type is validated but not file size. Users can attempt to upload arbitrarily large files, which will fail after a long wait with no clear error.

**Remediation:** Add a `MAX_FILE_SIZE` constant and validate before upload begins:

```typescript
const MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024; // 10 GB
if (file.size > MAX_FILE_SIZE) {
  setError(`File too large. Maximum size is ${formatBytes(MAX_FILE_SIZE)}`);
  return;
}
```

### 4.3 P1 — No resumable upload support *

**File:** `frontend/src/app/data/api.ts:352-406`

Uploads use a single XHR request. Network interruptions or browser refreshes require restarting the entire upload from scratch.

**Remediation:** Implement chunked/resumable uploads using the TUS protocol or a custom chunk-based approach with server-side reassembly.

### 4.4 P2 — Optimistic UI updates without rollback

**File:** `frontend/src/app/data/api-provider.tsx:225-284`

`updateCardFields()` and `updateCardStatus()` update local state immediately but catch API errors with only `console.error`. If the backend rejects the update, the UI shows stale data as saved.

**Remediation:** Implement proper optimistic update rollback: save previous state, apply optimistic update, revert on API failure, and show a toast notification.

### 4.5 P2 — Hardcoded per-page limit loads all cards on init

**File:** `frontend/src/app/data/api-provider.tsx:68,92`

`fetchCards({ perPage: 500 })` loads up to 500 cards at initialization. As the database grows, this causes slow initial loads and high memory usage.

**Remediation:** Implement proper pagination with infinite scroll or page navigation. Start with a smaller default (e.g., 50) and load more on demand.

### 4.6 P2 — Empty catch blocks in polling interval

**File:** `frontend/src/app/data/api-provider.tsx:138-140`

Errors in the polling interval callback are silently swallowed. If the backend goes down, the UI silently stops updating while appearing functional.

**Remediation:** Track consecutive polling failures. After N failures, show a connection-lost banner and stop polling.

### 4.7 P2 — No upload progress stall detection

**File:** `frontend/src/app/components/upload-video-dialog.tsx:74-80`

If the upload stalls (network issue without disconnect), the progress bar freezes with no timeout or user feedback.

**Remediation:** Add a stall timer: if progress hasn't changed in 30 seconds, show a warning and offer to retry or cancel.

### 4.8 P2 — Double-click on delete/submit triggers duplicate requests

**Files:** `frontend/src/app/pages/video-detail-page.tsx:33-60`, `frontend/src/app/pages/videos-page.tsx:11-23`

Async delete and submit operations don't disable their buttons during execution. Rapid clicks can trigger multiple API calls.

**Remediation:** Add loading states to mutation buttons; disable them while the request is in flight.

### 4.9 P2 — No unsaved-changes warning on navigation

**File:** `frontend/src/app/pages/ocr-review-verify-page.tsx:46-96`

The review form tracks `hasEdits` but never warns the user on navigation away. Edits are silently lost.

**Remediation:** Add a `beforeunload` event listener and a route-change prompt when `hasEdits` is true.

### 4.10 P2 — Missing security headers and source map exposure

**File:** `frontend/vite.config.ts`

No CSP headers configured. Source maps are not explicitly disabled for production builds, exposing source code.

**Remediation:** Disable source maps in production (`build: { sourcemap: false }`). Configure security headers (CSP, X-Frame-Options, X-Content-Type-Options) either in Vite's server config or in the reverse proxy.

### 4.11 P3 — Keyboard shortcuts documented but not implemented

**File:** `frontend/src/app/pages/ocr-review-verify-page.tsx:384-391`

The review page shows keyboard shortcut hints (A, F, S, J, K) but has no corresponding `keydown` event listeners.

**Remediation:** Implement the keyboard shortcut handlers or remove the hints to avoid user confusion.

---

## 5. Deployment & Operations

### 5.1 P1 — No health check endpoint

**File:** `src/southview/api/app.py`

No `/health` or `/healthz` endpoint exists. Load balancers, container orchestrators, and monitoring systems cannot determine service health.

**Remediation:** Add a health endpoint that checks database connectivity and returns version info:

```python
@app.get("/health")
def health():
    try:
        session = get_session()
        session.execute(text("SELECT 1"))
        session.close()
        return {"status": "ok", "version": "0.1.0"}
    except Exception:
        return JSONResponse({"status": "degraded"}, status_code=503)
```

### 5.2 P1 — No graceful shutdown handling

**File:** `src/southview/__main__.py:84-90`

No signal handlers or shutdown hooks. When the process is stopped, running job threads are killed mid-operation, potentially corrupting data.

**Remediation:** Use FastAPI's lifespan context manager to track active job threads and wait for them to complete (with a timeout) on shutdown. Mark any still-running jobs as interrupted.

### 5.3 P1 — No environment validation at startup

**File:** `src/southview/api/app.py:49-51`

The startup handler only calls `init_db()`. Missing `GEMINI_API_KEY`, `SOUTHVIEW_AUTH_PASSWORD_HASH`, or `SOUTHVIEW_AUTH_SESSION_SECRET` are not detected until the first relevant request fails.

**Remediation:** Validate all required configuration at startup and fail fast with clear error messages:

```python
@app.on_event("startup")
def startup():
    init_db(config["database"]["path"])
    validate_auth_configuration()
    validate_gemini_config()  # Check API key is set and non-empty
```

### 5.4 P1 — No production deployment artifacts

**Missing files:** `Dockerfile`, `docker-compose.yml`, `nginx.conf`, systemd unit files

No documented or automated deployment path exists. Production deployment requires significant manual setup with no reproducibility.

**Remediation:** Create at minimum a `Dockerfile` (multi-stage build: Node frontend build + Python backend), a `docker-compose.yml` with an nginx reverse proxy for TLS termination, and a deployment guide.

### 5.5 P1 — Dependency version pinning uses open-ended ranges

**File:** `pyproject.toml:10-23`

All Python dependencies use `>=` without upper bounds (e.g., `fastapi>=0.104.0`). A `pip install` today may install different versions than tomorrow, causing non-reproducible builds and potential breakage.

**Remediation:** Pin exact versions in a lock file. Use `pip-compile` (pip-tools) or `poetry.lock` to generate reproducible dependency locks. Commit the lock file.

### 5.6 P2 — No structured logging

**Files:** All Python modules using `logging.getLogger(__name__)`

Logs are unstructured text. In production, aggregating, searching, and alerting on logs requires structured (JSON) output.

**Remediation:** Configure `structlog` or `python-json-logger` with correlation IDs per request. Add a request ID middleware that tags all log entries.

### 5.7 P2 — No metrics or monitoring instrumentation

**File:** `src/southview/api/app.py`

No Prometheus metrics, no StatsD counters, no OpenTelemetry traces. Production issues (slow OCR, DB contention, memory leaks) will be invisible until users report them.

**Remediation:** Add `prometheus-fastapi-instrumentator` for automatic HTTP metrics. Add custom metrics for job processing time, OCR success rate, upload sizes, and queue depth.

### 5.8 P2 — Debug flags enabled in config

**File:** `config.yaml`

`save_intermediate_images: true`, `save_tesseract_dataframe: true`, and `sample_save_rate: 1` (saves every card) are debug settings that waste storage in production.

**Remediation:** Create environment-specific configs (`config.production.yaml`) with debug flags disabled. Override via environment variables.

### 5.9 P2 — Deprecated FastAPI event handlers

**File:** `src/southview/api/app.py:49-50`

`@app.on_event("startup")` is deprecated in modern FastAPI. It does not support cleanup on shutdown.

**Remediation:** Migrate to the lifespan context manager pattern:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(config["database"]["path"])
    yield
    # Cleanup: wait for job threads, close DB connections

app = FastAPI(lifespan=lifespan)
```

### 5.10 P2 — Frontend build not integrated with backend serving

**File:** `frontend/vite.config.ts:25-28`

The Vite proxy is hardcoded to `http://127.0.0.1:8000`. There is no documented production build process or environment-variable-based API URL configuration.

**Remediation:** Use a build-time environment variable for the API base URL. Document the production build and deployment workflow in a `DEPLOYMENT.md`.

### 5.11 P3 — No disk space monitoring during pipeline execution

**File:** `src/southview/ingest/video_upload.py:27-41`

Disk space is checked at upload time but not during frame extraction or OCR, which can generate significant intermediate data.

**Remediation:** Add periodic disk space checks during long-running pipeline operations. Abort gracefully with a clear error if disk is critically low.

### 5.12 P3 — No backup retention policy

**File:** `src/southview/backup/backup_manager.py`

Backups accumulate without automatic cleanup. Over time they consume significant disk space.

**Remediation:** Implement a retention policy (e.g., keep last N backups, or backups from last N days) with automatic pruning.

---

## Summary

| Severity | Count | Categories |
|----------|-------|------------|
| P0       | 6     | Path traversal (3), timing attack, race condition, destructive cleanup |
| P1       | 17    | Auth/CORS, rate limiting, event loop blocking, no retries, no deploys |
| P2       | 18    | Error handling, data integrity, UI reliability, observability |
| P3       | 5     | Disk monitoring, backup retention, keyboard shortcuts, restore verification |
| **Total** | **46** | |

### Recommended fix order

**Phase 1 — Security (do first, blocks any deployment):**
Issues 1.1 through 1.4 (P0 path traversals + timing attack), 1.5-1.11 (auth hardening, CORS, CSRF, rate limiting).

**Phase 2 — Data safety (do before any real data is loaded):**
Issues 2.1 (duplicate job race), 2.2 (destructive cleanup), 3.1-3.2 (SQLite limits, migration tooling).

**Phase 3 — Reliability (do before go-live):**
Issues 2.3-2.7 (retries, event loop, daemon threads, OCR resilience), 5.1-5.3 (health checks, graceful shutdown, startup validation).

**Phase 4 — Deployment (do for production launch):**
Issues 5.4-5.5 (Dockerfile, dependency pinning), 1.7 (configurable CORS), 5.10 (frontend build).

**Phase 5 — Hardening (do post-launch):**
All remaining P2/P3 issues: observability, metrics, UI polish, pagination, optimistic updates.
