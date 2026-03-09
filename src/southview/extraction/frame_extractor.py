"""Main frame extraction orchestrator."""

import logging
from pathlib import Path

import cv2
import numpy as np

from southview.config import get_config
from southview.extraction.scene_detect import detect_transitions
from southview.extraction.sharpness import compute_sharpness

logger = logging.getLogger(__name__)


def extract_frames(
    video_path: str | Path,
    video_id: str,
    output_dir: str | Path | None = None,
) -> list[dict]:
    """
    Extract one best frame per card from a video.

    Returns a list of dicts with keys: frame_number, image_path, sequence_index.
    """
    config = get_config()
    video_path = str(video_path)

    if output_dir is None:
        output_dir = Path(config["storage"]["frames_dir"]) / video_id
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    transitions = detect_transitions(video_path)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Build segments: ranges between transitions
    boundaries = [0] + transitions + [total_frames]
    segments = [
        (boundaries[i], boundaries[i + 1]) for i in range(len(boundaries) - 1)
    ]

    min_stable = config["frame_extraction"]["min_stable_frames"]
    blank_threshold = config["frame_extraction"].get("blank_threshold", 50.0)
    results = []

    for seq_idx, (start, end) in enumerate(segments):
        if (end - start) < min_stable:
            continue

        best_frame, best_frame_num = _find_best_frame(cap, start, end)
        if best_frame is None:
            continue

        # Skip blank/empty frames (e.g. empty hopper)
        sharpness = compute_sharpness(best_frame)
        if sharpness < blank_threshold:
            logger.info(
                f"Skipping segment {seq_idx + 1} (frame {best_frame_num}): "
                f"below blank threshold ({sharpness:.1f} < {blank_threshold})"
            )
            continue

        filename = f"card_{seq_idx + 1:04d}.jpg"
        image_path = output_dir / filename
        cv2.imwrite(str(image_path), best_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

        results.append({
            "frame_number": best_frame_num,
            "image_path": str(image_path),
            "sequence_index": seq_idx + 1,
        })

    cap.release()
    return results


def _find_best_frame(
    cap: cv2.VideoCapture, start: int, end: int
) -> tuple[np.ndarray | None, int]:
    """Find the sharpest frame in a range."""
    best_sharpness = -1.0
    best_frame = None
    best_num = start

    # Sample the middle 60% of the segment to avoid transition edges
    margin = int((end - start) * 0.2)
    sample_start = start + margin
    sample_end = end - margin

    cap.set(cv2.CAP_PROP_POS_FRAMES, sample_start)

    for frame_num in range(sample_start, sample_end):
        ret, frame = cap.read()
        if not ret:
            break
        sharpness = compute_sharpness(frame)
        if sharpness > best_sharpness:
            best_sharpness = sharpness
            best_frame = frame.copy()
            best_num = frame_num

    return best_frame, best_num
