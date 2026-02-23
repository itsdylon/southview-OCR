"""Frame sharpness metrics for best-frame selection."""

import cv2
import numpy as np


def compute_sharpness(frame: np.ndarray) -> float:
    """
    Compute sharpness score using Laplacian variance.

    Higher values indicate sharper images.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    return float(laplacian.var())
