"""Video metadata extraction using OpenCV."""

from pathlib import Path

import cv2


def extract_video_metadata(file_path: str | Path) -> dict:
    """Extract metadata from a video file."""
    file_path = str(file_path)
    cap = cv2.VideoCapture(file_path)

    if not cap.isOpened():
        raise ValueError(f"Could not open video: {file_path}")

    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0.0

        return {
            "fps": fps,
            "frame_count": frame_count,
            "resolution_w": width,
            "resolution_h": height,
            "duration_seconds": duration,
        }
    finally:
        cap.release()
