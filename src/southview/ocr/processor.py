from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import cv2

from southview.ocr.preprocess import preprocess_array
from southview.ocr.tesseract_wrapper import run_tesseract
from southview.ocr.parser import parse_fields
from southview.ocr.confidence import add_confidence


def process_card(
    image_path: str | Path,
    *,
    debug_dir: Optional[str] = None,
    tesseract_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Production entry point (preprocess in memory, no disk writes by default):

      read -> preprocess_array -> OCR -> parse -> confidence

    debug_dir:
      If provided, preprocess_array will save debug stage images into this directory.
      In production, leave this as None.
    """
    image_path = Path(image_path)

    # 1) Read original image
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    # 2) Preprocess in-memory (optional debug saving handled inside preprocess_array)
    img_for_ocr = preprocess_array(img, debug_dir=debug_dir)

    # 3) OCR
    tkw = tesseract_kwargs or {}
    ocr = run_tesseract(img_for_ocr, **tkw) if tkw else run_tesseract(img_for_ocr)
    words = ocr.get("words", []) or []

    # 4) Parse
    parsed = parse_fields(words)

    # 5) Confidence
    result = add_confidence(parsed, words)

    # Meta (helpful for logging/debugging)
    result["meta"] = {
        "image_path": str(image_path),
        "debug_dir": debug_dir,
        "num_words": len(words),
    }

    return result