"""Scene/card boundary detection using histogram comparison."""

import cv2
import numpy as np

from southview.config import get_config


def detect_transitions(video_path: str) -> list[int]:
    """
    Detect frame numbers where card transitions occur.

    Uses histogram comparison between sampled frames to find scene changes.
    Returns list of frame numbers where transitions were detected.
    """
    config = get_config()
    sample_rate = config["frame_extraction"]["sample_rate"]
    threshold = config["frame_extraction"]["transition_threshold"]

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    # Auto-rotate frames based on video rotation metadata
    cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)

    transitions = []
    prev_hist = None
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % sample_rate == 0:
            hist = _compute_histogram(frame)

            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
                if diff > threshold:
                    transitions.append(frame_idx)

            prev_hist = hist

        frame_idx += 1

    cap.release()
    return transitions


def _compute_histogram(frame: np.ndarray) -> np.ndarray:
    """Compute a normalized grayscale histogram for a frame."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    cv2.normalize(hist, hist)
    return hist
