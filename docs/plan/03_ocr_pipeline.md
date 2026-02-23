# Subplan 3: OCR Pipeline

## Goal
Extract text from card images with word-level confidence scoring, handling both typed and handwritten text.

## Scope
- Image pre-processing for OCR quality
- Tesseract OCR execution with confidence output
- Word-level and card-level confidence computation
- OCRResult record creation

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

## Typed vs Handwritten

Tesseract with LSTM (oem 1) handles typed text well. Handwritten text will:
- Generally produce lower confidence scores
- Naturally get flagged for review via the confidence threshold
- No special mode needed — the confidence system handles this gracefully

If handwritten accuracy is too low, a future enhancement could add a specialized handwriting model (e.g., TrOCR), but Tesseract is the pragmatic starting point.

## Key Functions
```
process_card(card: Card) -> OCRResult
preprocess_image(image: np.ndarray) -> np.ndarray
run_tesseract(image: np.ndarray) -> TesseractOutput
compute_confidence(word_data: list[dict]) -> float
extract_word_confidences(tesseract_data: pd.DataFrame) -> list[dict]
```

## Batch Processing
- Process cards sequentially within a video (memory-efficient)
- Update job progress after each card
- Store results incrementally (don't wait for entire batch)

## Error Handling
- Tesseract crash on a single card → log error, mark card as failed, continue batch
- Empty OCR result (no text found) → store empty result, confidence = 0.0, flag for review
- Image too small/corrupt → skip with error, flag for review

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
