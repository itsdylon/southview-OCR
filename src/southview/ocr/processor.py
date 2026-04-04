from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import cv2

from southview.ocr.confidence import add_confidence
from southview.ocr.engine import get_ocr_engine_version, run_ocr, uses_rotation_sweep
from southview.ocr.parser import parse_fields
from southview.ocr.parser_min import parse_fields_min
from southview.ocr.preprocess import preprocess_array

logger = logging.getLogger(__name__)

_ORIENTATIONS = [
    (0, None),
    (90, cv2.ROTATE_90_CLOCKWISE),
    (180, cv2.ROTATE_180),
    (270, cv2.ROTATE_90_COUNTERCLOCKWISE),
]


def _avg_word_confidence(words: list[dict]) -> float:
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


def _normalize_parsed_fields(parsed: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}
    for key, value in parsed.items():
        if isinstance(value, dict):
            normalized[key] = {
                "value": value.get("value"),
                "support": value.get("support", []) or [],
            }
        else:
            normalized[key] = {"value": value, "support": []}
    return normalized


def _run_ocr(img, debug_dir=None, tesseract_kwargs=None):
    img_for_ocr = preprocess_array(img, debug_dir=debug_dir)
    ocr = run_ocr(img_for_ocr)
    words = ocr.get("words", []) or []
    raw_text = ocr.get("raw_text", "") or ""
    parsed = ocr.get("fields") or (parse_fields_min(words, raw_text=raw_text) if raw_text and not words else parse_fields(words))
    parsed = _normalize_parsed_fields(parsed)

    if ocr.get("fields"):
        result = {
            "fields": {k: v.get("value") for k, v in parsed.items()},
            "field_support": {k: v.get("support", []) for k, v in parsed.items()},
            "field_confidence": ocr.get("field_confidence") or {},
            "card_confidence": float(ocr.get("card_confidence", 0.0) or 0.0),
        }
    else:
        result = add_confidence(parsed, words)

    return result, words


def process_card(
    image_path: str | Path,
    *,
    debug_dir: Optional[str] = None,
    tesseract_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    image_path = Path(image_path)

    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    if not uses_rotation_sweep():
        best_result, best_words = _run_ocr(
            img,
            debug_dir=debug_dir,
            tesseract_kwargs=tesseract_kwargs,
        )
        best_degree = 0
    else:
        best_conf = -1.0
        best_result = None
        best_words = []
        best_degree = 0

        for degree, rotate_flag in _ORIENTATIONS:
            rotated = img if rotate_flag is None else cv2.rotate(img, rotate_flag)
            d_dir = f"{debug_dir}_{degree}" if debug_dir and degree != 0 else debug_dir
            result, words = _run_ocr(
                rotated,
                debug_dir=d_dir,
                tesseract_kwargs=tesseract_kwargs,
            )
            conf = _avg_word_confidence(words)

            if conf > best_conf:
                best_conf = conf
                best_result = result
                best_words = words
                best_degree = degree

        if best_degree != 0:
            logger.info(
                "Card %s: %d degrees selected (conf %.3f)",
                image_path,
                best_degree,
                best_conf,
            )

    best_result["meta"] = {
        "image_path": str(image_path),
        "debug_dir": debug_dir,
        "num_words": len(best_words),
        "orientation": best_degree,
        "ocr_engine_version": get_ocr_engine_version(),
    }

    return best_result
