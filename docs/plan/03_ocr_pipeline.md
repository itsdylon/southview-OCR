# Subplan 3: OCR Pipeline

## Goal
Extract structured field data from card images with word-level confidence scoring. Cards are pre-printed forms filled via typewriter.

## Scope
- Image pre-processing for OCR quality
- Tesseract OCR execution with confidence output
- **Structured field extraction** — parse OCR output into known card fields
- Word-level and card-level confidence computation
- OCRResult record creation with both raw text and structured fields

## Pre-Processing Pipeline

Each card image goes through these steps before OCR:

1. **Grayscale conversion** — remove color noise
2. **Deskew** — detect and correct rotation (important for scanned cards at angles)
3. **Contrast enhancement** — adaptive histogram equalization (CLAHE)
4. **Noise reduction** — Gaussian blur or bilateral filter (light touch)
5. **Binarization** — Otsu's or adaptive thresholding
6. **Border removal** — crop to content region if card has dark borders

### Pre-Processing Config
```yaml
ocr:
  preprocessing:
    deskew: true
    clahe_clip_limit: 2.0
    clahe_grid_size: 8
    denoise: true
    denoise_strength: 10
    binarize: true
    binarize_method: otsu  # otsu | adaptive
```

## Tesseract Configuration

### Engine Mode
- `--oem 1` — LSTM neural net only (best accuracy for mixed typed/handwritten)
- `--psm 6` — Assume a single uniform block of text (good for index cards)

### Confidence Extraction
Tesseract's `image_to_data()` returns per-word data including:
- `text` — recognized word
- `conf` — confidence (0–100, -1 for non-text elements)
- `left, top, width, height` — bounding box
- `block_num, par_num, line_num, word_num` — structural position

### Language
- Default: `eng` (English)
- Configurable for other card collections

## Confidence Scoring

### Word-Level
- Direct from Tesseract: 0–100 integer
- Stored as JSON array in `word_confidences`:
  ```json
  [
    {"text": "Smith", "confidence": 95, "bbox": [10, 20, 80, 40]},
    {"text": "John", "confidence": 92, "bbox": [90, 20, 150, 40]},
    {"text": "1923", "confidence": 78, "bbox": [10, 50, 70, 70]}
  ]
  ```

### Card-Level
- Computed as: mean of all word confidences (excluding -1 values), divided by 100
- Range: 0.0 – 1.0
- If no words detected: confidence = 0.0

### Thresholds (Configurable)
```yaml
ocr:
  confidence:
    auto_approve: 0.85    # Cards above this are auto-approved
    review_threshold: 0.70 # Cards below this are flagged
```

## Card Field Structure

These are historical cemetery index cards. They are pre-printed forms filled in via typewriter. The fields are:

| Field | Label on Card | Position | Notes |
|-------|--------------|----------|-------|
| deceased_name | *(unlabeled)* | Top line, prominent | Often "LAST, First Middle" format |
| address | *(unlabeled)* | Same line as name, right side | Street address, city, state |
| owner | "Owner" | Below header | Lot/estate owner name |
| relation | "Relation:" | Right of owner | Owner's relation to deceased |
| phone | "Ph#" | Near owner line | Not always present |
| date_of_death | "Date of death" | Mid-card | **Often missing** on older cards |
| date_of_burial | "Date of burial" | Right of date_of_death | Various date formats |
| description | "Description:" | Below dates | Grave location (lot#, range, grave#, section, block, side) |
| sex | "Sex" | Below description | M or F |
| age | "Age" | Right of sex | Numeric |
| grave_type | "Type of Grave" | Right of age | e.g., "SVC Vault", "Thrasher OS" |
| grave_fee | "Grave Fee" | Right end of line | Dollar amount |
| undertaker | "Undertaker" | Below sex/age line | Funeral home/person name |
| board_of_health_no | "Board of Health No." | Right of undertaker | Older cards only |
| svc_no | "SVC No." | Bottom of card | Service number |

### Key Characteristics
- **All text is typewritten** — good for Tesseract accuracy
- **Positions vary slightly** — typewriter alignment shifts mean text may be offset from expected positions
- **Many fields are optional** — especially date_of_death, phone, board_of_health_no, grave_fee
- **Text typed over pre-printed lines** — typewriter sometimes shifted, causing text to overlap form lines
- **Card eras differ** — older cards (1940s) have fewer fields; newer cards (2000s+) include phone, contact info, date of birth
- **Handwritten annotations** — some cards have red/blue ink notes added later (lower priority; may produce low-confidence OCR)

## Field Extraction Strategy

### Approach: Full OCR + Label-Based Parsing

Template-based region extraction is unreliable because card positions vary. Instead:

1. **Full-card OCR**: Run Tesseract on the entire card image → get all words with bounding boxes and confidences
2. **Label detection**: Scan OCR output for known label keywords ("Owner", "Relation:", "Date of death", "Date of burial", "Description:", "Sex", "Age", "Type of Grave", "Grave Fee", "Undertaker", "Board of Health No.", "SVC No.")
3. **Value association**: For each detected label, extract the text that follows it on the same line or nearby region
4. **Header extraction**: The top of the card is special — no labels. The deceased name is the first/prominent text, and the address follows to the right
5. **Store results**: Populate structured fields in `OCRResult`; preserve originals in `raw_fields_json`

### Parsing Rules
- **Name**: First line of text, typically in "LAST, First" format. May be underlined on the form.
- **Address**: Text to the right of the name on the top line(s), typically a street + city + state
- **Label → Value**: For labeled fields, the value is the text on the same line following the label (or between this label and the next)
- **Missing fields**: If a label is found but no typed text follows, the field is stored as null
- **Dates**: Accept multiple formats (e.g., "December 8, 2004", "3-20-41", "12/8/04")

### Fallback
If label detection fails or produces poor results, the full `raw_text` is always preserved. The reviewer can manually populate fields during review.

## Typed vs Handwritten

The primary content is typewritten and Tesseract handles it well. Handwritten annotations (often in red/blue ink) will:
- Generally produce lower confidence scores
- Naturally get flagged for review via the confidence threshold
- Are lower priority — the typed fields are the core data

If handwritten accuracy is too low, a future enhancement could add a specialized handwriting model (e.g., TrOCR), but Tesseract is the pragmatic starting point.

## Key Functions
```
process_card(card: Card) -> OCRResult
preprocess_image(image: np.ndarray) -> np.ndarray
run_tesseract(image: np.ndarray) -> TesseractOutput
compute_confidence(word_data: list[dict]) -> float
extract_word_confidences(tesseract_data: pd.DataFrame) -> list[dict]
parse_card_fields(word_data: list[dict]) -> dict[str, str | None]
extract_header(word_data: list[dict]) -> tuple[str, str]  # (name, address)
find_label_value(label: str, word_data: list[dict]) -> str | None
```

## Batch Processing
- Process cards sequentially within a video (memory-efficient)
- Update job progress after each card
- Store results incrementally (don't wait for entire batch)

## Error Handling
- Tesseract crash on a single card → log error, mark card as failed, continue batch
- Empty OCR result (no text found) → store empty result, confidence = 0.0, flag for review
- Image too small/corrupt → skip with error, flag for review
- Field parsing failure → store raw_text, leave structured fields null, flag for review

## Files to Create
- `src/southview/ocr/processor.py` — main OCR orchestrator
- `src/southview/ocr/preprocess.py` — image pre-processing pipeline
- `src/southview/ocr/confidence.py` — confidence computation
- `src/southview/ocr/tesseract_wrapper.py` — Tesseract interface
- Tests in `tests/test_ocr/`

## Dependencies
- pytesseract
- Tesseract binary (system install)
- Pillow
- OpenCV
- NumPy
