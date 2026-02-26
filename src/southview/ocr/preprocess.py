"""Image pre-processing pipeline for OCR quality improvement."""

from pathlib import Path

import cv2
import numpy as np

from southview.config import get_config

import os

def _save_dbg(img: np.ndarray, debug_dir: str | None, name: str) -> None:
    if not debug_dir:
        return
    os.makedirs(debug_dir, exist_ok=True)
    cv2.imwrite(str(Path(debug_dir) / name), img)
def preprocess_image(image_path: str | Path, debug_dir: str | None = None) -> np.ndarray:
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")
    return preprocess_array(image, debug_dir=debug_dir)
# def preprocess_image(image_path: str | Path, debug_dir: str | None = None) -> np.ndarray:
#     """Apply the full pre-processing pipeline to a card image."""
#     config = get_config()
#     pp_config = config["ocr"]["preprocessing"]

#     image = cv2.imread(str(image_path))
#     if image is None:
#         raise ValueError(f"Could not read image: {image_path}")

#     # Convert to grayscale
#     gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

#     _save_dbg(gray, debug_dir, "01_gray.png")

#     # Deskew
#     if pp_config.get("deskew", True):
#         gray = _deskew(gray)
    
#     _save_dbg(gray, debug_dir, "02_deskew.png")

#     # Contrast enhancement (CLAHE)
#     clip_limit = pp_config.get("clahe_clip_limit", 2.0)
#     grid_size = pp_config.get("clahe_grid_size", 8)
#     clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(grid_size, grid_size))
#     gray = clahe.apply(gray)

#     _save_dbg(gray, debug_dir, "03_clahe.png")

#     # Denoise
#     if pp_config.get("denoise", True):
#         strength = pp_config.get("denoise_strength", 10)
#         gray = cv2.fastNlMeansDenoising(gray, h=strength)
    
#     _save_dbg(gray, debug_dir, "04_denoise.png")

#     # Binarize
#     if pp_config.get("binarize", True):
#         method = pp_config.get("binarize_method", "otsu")
#         if method == "adaptive":
#             gray = cv2.adaptiveThreshold(
#                 gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
#             )
#         else:
#             _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
#     _save_dbg(gray, debug_dir, "05_binary.png")

#     return gray
def preprocess_array(image: np.ndarray, debug_dir: str | None = None) -> np.ndarray:
    config = get_config()
    pp_config = config["ocr"]["preprocessing"]

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _save_dbg(gray, debug_dir, "01_gray.png")

    if pp_config.get("deskew", True):
        gray = _deskew(gray)
    _save_dbg(gray, debug_dir, "02_deskew.png")

    clip_limit = pp_config.get("clahe_clip_limit", 2.0)
    grid_size = pp_config.get("clahe_grid_size", 8)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(grid_size, grid_size))
    gray = clahe.apply(gray)
    _save_dbg(gray, debug_dir, "03_clahe.png")

    if pp_config.get("denoise", True):
        strength = pp_config.get("denoise_strength", 10)
        gray = cv2.fastNlMeansDenoising(gray, h=strength)
    _save_dbg(gray, debug_dir, "04_denoise.png")

    if pp_config.get("binarize", True):
        method = pp_config.get("binarize_method", "otsu")
        if method == "adaptive":
            gray = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
        else:
            _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _save_dbg(gray, debug_dir, "05_binary.png")

    return gray

# def _deskew(image: np.ndarray) -> np.ndarray:
#     """Correct image rotation using minimum area rectangle of contours."""
#     coords = np.column_stack(np.where(image > 0))
#     if len(coords) < 10:
#         return image

#     angle = cv2.minAreaRect(coords)[-1]

#     if angle < -45:
#         angle = -(90 + angle)
#     else:
#         angle = -angle

#     if abs(angle) < 0.5:
#         return image

#     h, w = image.shape[:2]
#     center = (w // 2, h // 2)
#     matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
#     rotated = cv2.warpAffine(
#         image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
#     )
#     return rotated

def _deskew(image: np.ndarray) -> np.ndarray:
    """Correct image rotation using min-area-rect on foreground (text) pixels."""
    # Binarize for skew detection only (text should be foreground)
    _, bw = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    inv = 255 - bw  # text -> white

    coords = cv2.findNonZero(inv)
    if coords is None or len(coords) < 50:
        return image

    angle = cv2.minAreaRect(coords)[-1]  # in [-90, 0)
    if angle < -45:
        angle = 90 + angle

    if abs(angle) < 0.5:
        return image

    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
    rotated = cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return rotated