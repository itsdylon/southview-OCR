# Subplan 5: Review Workflow

## Goal
Enable a human reviewer to view, correct, and approve OCR results through API endpoints consumed by the frontend.

## Scope
- Card listing with filters (by video, by review status, by confidence)
- Card detail view (image + OCR text + confidence)
- Text correction and approval
- Review status state machine

## Review Status State Machine

```
                  OCR Complete
                      │
            ┌─────────┴──────────┐
            ▼                    ▼
    ┌───────────┐        ┌───────────┐
    │  PENDING  │        │  FLAGGED  │  (confidence < threshold)
    └─────┬─────┘        └─────┬─────┘
          │                    │
          │  reviewer action   │
          ▼                    ▼
    ┌───────────┐        ┌───────────┐
    │ APPROVED  │        │ CORRECTED │  (text was edited)
    └───────────┘        └───────────┘
```

- **pending**: OCR done, confidence above flag threshold, awaiting review
- **flagged**: OCR done, confidence below flag threshold, priority review needed
- **approved**: Reviewer confirmed the OCR text is correct
- **corrected**: Reviewer edited the text (corrected_text is populated)

High-confidence cards (>= auto_approve threshold) can be auto-set to `approved` if configured.

## API Endpoints

### List Cards for Review
```
GET /api/cards?video_id=...&status=...&min_confidence=...&max_confidence=...&page=...&per_page=...
```
Returns paginated card list with summary info.

**Sort options**: confidence (asc for worst-first review), sequence_index, review_status

### Card Detail
```
GET /api/cards/{card_id}
```
Returns:
- Card metadata (video, sequence, frame number)
- Image URL (served as static file)
- OCR result: all structured fields (deceased_name, address, owner, relation, phone, date_of_death, date_of_burial, description, sex, age, grave_type, grave_fee, undertaker, board_of_health_no, svc_no)
- Raw text and raw_fields_json (original OCR extraction)
- Confidence score and word confidences
- Review status

### Submit Review
```
PUT /api/cards/{card_id}/review
Body: {
  "fields": {                     // optional — per-field corrections
    "deceased_name": "AARON, Benjamin L.",
    "date_of_death": "December 8, 2004",
    ...                           // only include fields being corrected
  },
  "status": "approved",           // "approved" or "corrected"
  "reviewed_by": "reviewer1"      // optional reviewer name
}
```

Validation:
- If any `fields` are provided and differ from current values, status must be `corrected`
- If no field changes, status should be `approved`
- Only provided fields are updated; omitted fields are left unchanged
- `reviewed_at` is auto-set to now

### Batch Review
```
PUT /api/cards/batch-review
Body: {
  "card_ids": ["...", "..."],
  "status": "approved",
  "reviewed_by": "reviewer1"
}
```
For bulk-approving high-confidence cards. Does not support per-field corrections (use individual review for that).

## Review Statistics
```
GET /api/stats
```
Returns:
- Total cards
- Cards by status (pending, flagged, approved, corrected)
- Cards by video
- Average confidence
- Review progress percentage

## Image Serving
Card images served as static files:
```
GET /static/frames/{video_id}/card_{NNN}.png
```
FastAPI `StaticFiles` mount on the `data/frames/` directory.

## Files to Create
- `src/southview/api/routes/cards.py` — card endpoints
- `src/southview/api/routes/stats.py` — statistics endpoint
- `src/southview/review/service.py` — review business logic
- Tests in `tests/test_review/`
