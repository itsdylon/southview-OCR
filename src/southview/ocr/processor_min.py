# src/southview/ocr/processor_min.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import cv2

from southview.ocr.preprocess import preprocess_array
from southview.ocr.tesseract_wrapper import run_tesseract
from southview.ocr.parser_min import parse_fields_min

# ----------------------------
# confidence helpers (minimal)
# ----------------------------
def _bbox_iou(a: List[int], b: List[int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    a_area = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    b_area = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = a_area + b_area - inter
    return inter / union if union > 0 else 0.0

def _word_conf(w: Dict[str, Any]) -> float:
    c = w.get("conf", w.get("confidence", 0))
    try:
        return float(c) / 100.0
    except Exception:
        return 0.0

def _confidence_for_support(words: List[Dict[str, Any]], support_bboxes: List[List[int]]) -> float:
    if not support_bboxes:
        return 0.0

    matched: List[float] = []
    for sb in support_bboxes:
        best = 0.0
        best_conf = 0.0
        for w in words:
            if "bbox" not in w:
                continue
            iou = _bbox_iou(sb, w["bbox"])
            if iou > best:
                best = iou
                best_conf = _word_conf(w)
        if best >= 0.3:
            matched.append(best_conf)

    if not matched:
        return 0.0
    return sum(matched) / len(matched)

def _card_confidence(field_conf: Dict[str, float]) -> float:
    # simple average over existing keys
    if not field_conf:
        return 0.0
    return sum(field_conf.values()) / len(field_conf)

# ----------------------------
# public entry point
# ----------------------------
def process_card_min(image_path: str) -> Dict[str, Any]:
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    pre = preprocess_array(img)              # preprocess but does NOT write files
    ocr = run_tesseract(pre)                 # OCR on preprocessed array
    words = ocr.get("words", [])
    raw_text = ocr.get("raw_text", "")

    parsed = parse_fields_min(words, raw_text=raw_text)

    fields = {k: parsed[k]["value"] for k in parsed}
    field_support = {k: parsed[k]["support"] for k in parsed}
    field_confidence = {k: _confidence_for_support(words, field_support[k]) for k in parsed}

    for k in fields:
        if fields[k] is None or str(fields[k]).strip() == "":
            field_confidence[k] = 0.0
            field_support[k] = []
    # If a field is missing, keep conf at 0.0 (that’s correct for “unknown”)
    card_confidence = _card_confidence(field_confidence)

    return {
        "fields": fields,
        "field_support": field_support,
        "field_confidence": field_confidence,
        "card_confidence": card_confidence,
        "raw_text": raw_text,
    }