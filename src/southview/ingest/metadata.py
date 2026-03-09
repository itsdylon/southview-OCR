"""Video metadata extraction using OpenCV."""

import struct
from pathlib import Path

import cv2


def _fourcc_to_str(fourcc_code: float) -> str:
    """Convert a numeric FourCC code to its 4-character string representation."""
    int_code = int(fourcc_code)
    if int_code <= 0:
        return ""
    return struct.pack("<I", int_code).decode("ascii", errors="replace").strip()


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
        codec = _fourcc_to_str(cap.get(cv2.CAP_PROP_FOURCC))

        rotation = cap.get(cv2.CAP_PROP_ORIENTATION_META)

        return {
            "fps": fps,
            "frame_count": frame_count,
            "resolution_w": width,
            "resolution_h": height,
            "duration_seconds": duration,
            "codec": codec,
            "rotation": int(rotation) if rotation else 0,
        }
    finally:
        cap.release()
