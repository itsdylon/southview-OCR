# Subplan 2: Frame Extraction

## Goal
Extract one high-quality still image per index card from each video.

## Scope
- Scene/card boundary detection
- Best-frame selection (sharpest, most stable)
- Image output as PNG
- Card record creation in database

## The Challenge
iPhone video of index cards being shown sequentially means:
- Cards are placed, held still briefly, then replaced
- Transitions between cards (hand movement, blur)
- Variable lighting, angle, distance
- We need to identify the "stable" moment for each card and grab the best frame

## Detection Strategy

### Approach: Histogram-Based Scene Detection + Stability Window

1. **Read video frame-by-frame** (or sample every Nth frame for speed)
2. **Compute frame difference** between consecutive frames using histogram comparison
3. **Detect transitions**: Large histogram difference = card change
4. **Identify stable windows**: Sequence of similar frames between transitions
5. **Select best frame** from each stable window:
   - Compute Laplacian variance (sharpness metric)
   - Pick the sharpest frame in the stable window

### Parameters (Configurable)
```yaml
frame_extraction:
  sample_rate: 3              # Process every Nth frame (speed vs accuracy)
  transition_threshold: 0.4   # Histogram diff threshold for scene change
  min_stable_frames: 5        # Minimum stable frames to count as a card
  sharpness_method: laplacian # Sharpness metric
```

### Tuning
These parameters will need tuning based on actual video characteristics. The config-driven approach allows adjustment without code changes.

## Processing Steps

1. Open video with `cv2.VideoCapture`
2. Sample frames at configured rate
3. For each frame pair, compute histogram difference
4. Mark transition points where difference > threshold
5. Between transitions, find the stable window
6. For the stable window, compute sharpness of each frame
7. Save the sharpest frame as `data/frames/{video_id}/card_{NNN}.png`
8. Create `Card` record in database with frame number, image path, sequence index

## Image Output
- Format: PNG (lossless, suitable for OCR)
- Naming: `card_{sequence_index:04d}.png` (zero-padded)
- Location: `data/frames/{video_id}/`

## Key Functions
```
extract_frames(video_path: str, video_id: str) -> list[Card]
detect_transitions(video_path: str) -> list[int]  # frame numbers
find_best_frame(video_path: str, start_frame: int, end_frame: int) -> np.ndarray
compute_sharpness(frame: np.ndarray) -> float
save_frame(frame: np.ndarray, output_path: str) -> str
```

## Edge Cases
- Very short stable windows (card shown briefly) → use `min_stable_frames` threshold
- No transitions detected (single card video) → treat entire video as one card
- Video starts/ends mid-card → handle first/last segments
- Blurry video throughout → extract best available, flag low sharpness

## Performance
- RTX 3090 can accelerate OpenCV video decode via CUDA
- For a 10-minute video at 30fps = 18,000 frames
- At sample_rate=3, processing 6,000 frames — should complete in seconds

## Files to Create
- `src/southview/extraction/frame_extractor.py` — main extraction logic
- `src/southview/extraction/scene_detect.py` — transition detection
- `src/southview/extraction/sharpness.py` — frame quality metrics
- Tests in `tests/test_extraction/`

## Dependencies
- OpenCV (`opencv-python-headless`)
- NumPy
