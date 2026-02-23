"""Image pre-processing pipeline for OCR quality improvement."""

from pathlib import Path

import cv2
import numpy as np

from southview.config import get_config


def preprocess_image(image_path: str | Path) -> np.ndarray:
    """Apply the full pre-processing pipeline to a card image."""
    config = get_config()
    pp_config = config["ocr"]["preprocessing"]

    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Deskew
    if pp_config.get("deskew", True):
        gray = _deskew(gray)

    # Contrast enhancement (CLAHE)
    clip_limit = pp_config.get("clahe_clip_limit", 2.0)
    grid_size = pp_config.get("clahe_grid_size", 8)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(grid_size, grid_size))
    gray = clahe.apply(gray)

    # Denoise
    if pp_config.get("denoise", True):
        strength = pp_config.get("denoise_strength", 10)
        gray = cv2.fastNlMeansDenoising(gray, h=strength)

    # Binarize
    if pp_config.get("binarize", True):
        method = pp_config.get("binarize_method", "otsu")
        if method == "adaptive":
            gray = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
        else:
            _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return gray


def _deskew(image: np.ndarray) -> np.ndarray:
    """Correct image rotation using minimum area rectangle of contours."""
    coords = np.column_stack(np.where(image > 0))
    if len(coords) < 10:
        return image

    angle = cv2.minAreaRect(coords)[-1]

    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) < 0.5:
        return image

    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return rotated
