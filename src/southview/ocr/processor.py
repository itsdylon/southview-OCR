from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import cv2

from southview.ocr.preprocess import preprocess_array
from southview.ocr.tesseract_wrapper import run_tesseract
from southview.ocr.parser import parse_fields
from southview.ocr.confidence import add_confidence

logger = logging.getLogger(__name__)


# (degree, OpenCV rotation flag) — None means no rotation needed
_ORIENTATIONS = [
    (0,   None),
    (90,  cv2.ROTATE_90_CLOCKWISE),
    (180, cv2.ROTATE_180),
    (270, cv2.ROTATE_90_COUNTERCLOCKWISE),
]


def _avg_word_confidence(words: list[dict]) -> float:
    """Average Tesseract word confidence (0-1)."""
    if not words:
        return 0.0
    confs = []
    for w in words:
        c = w.get("conf", w.get("confidence", 0))
        try:
            confs.append(float(c) / 100.0)
        except Exception:
            pass
    return sum(confs) / len(confs) if confs else 0.0


def _run_ocr(img, debug_dir=None, tesseract_kwargs=None):
    """Preprocess -> OCR -> parse -> confidence for a single orientation."""
    img_for_ocr = preprocess_array(img, debug_dir=debug_dir)
    tkw = tesseract_kwargs or {}
    ocr = run_tesseract(img_for_ocr, **tkw) if tkw else run_tesseract(img_for_ocr)
    words = ocr.get("words", []) or []
    parsed = parse_fields(words)
    result = add_confidence(parsed, words)
    return result, words


def process_card(
    image_path: str | Path,
    *,
    debug_dir: Optional[str] = None,
    tesseract_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Production entry point with multi-angle orientation detection.

    Tries all 4 orientations (0°, 90°, 180°, 270°) and picks the one
    with the highest average word confidence.

    debug_dir:
      If provided, preprocess_array will save debug stage images into this directory.
      In production, leave this as None.
    """
    image_path = Path(image_path)

    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    best_conf = -1.0
    best_result = None
    best_words = []
    best_degree = 0

    for degree, rotate_flag in _ORIENTATIONS:
        rotated = img if rotate_flag is None else cv2.rotate(img, rotate_flag)
        d_dir = f"{debug_dir}_{degree}" if debug_dir and degree != 0 else debug_dir
        result, words = _run_ocr(rotated, debug_dir=d_dir, tesseract_kwargs=tesseract_kwargs)
        conf = _avg_word_confidence(words)

        if conf > best_conf:
            best_conf = conf
            best_result = result
            best_words = words
            best_degree = degree

    if best_degree != 0:
        logger.info(
            "Card %s: %d° selected (conf %.3f)",
            image_path, best_degree, best_conf,
        )

    best_result["meta"] = {
        "image_path": str(image_path),
        "debug_dir": debug_dir,
        "num_words": len(best_words),
        "orientation": best_degree,
    }

    return best_result