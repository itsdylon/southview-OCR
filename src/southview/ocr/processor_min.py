from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from southview.config import get_config
from southview.ocr.engine import get_ocr_engine_name, get_ocr_engine_version, run_ocr, uses_rotation_sweep
from southview.ocr.gemini_wrapper import parse_structured_fields_with_gemini
from southview.ocr.parser_min import parse_fields_min
from southview.ocr.preprocess import preprocess_array

logger = logging.getLogger(__name__)

_ORIENTATIONS: List[Tuple[int, Any]] = [
    (0, None),
    (90, cv2.ROTATE_90_CLOCKWISE),
    (180, cv2.ROTATE_180),
    (270, cv2.ROTATE_90_COUNTERCLOCKWISE),
]

_SIDEWAYS_ORIENTATIONS: List[Tuple[int, Any]] = [
    (90, cv2.ROTATE_90_CLOCKWISE),
    (270, cv2.ROTATE_90_COUNTERCLOCKWISE),
]

_CORE_CONFIDENCE_WEIGHTS: Dict[str, float] = {
    "owner_name": 1.25,
    "date_of_death": 1.1,
    "date_of_burial": 1.0,
    "description": 1.0,
    "sex": 0.65,
    "age": 0.65,
    "undertaker": 0.6,
    "svc_no": 0.5,
}


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


def _confidence_for_support(
    words: List[Dict[str, Any]],
    support_bboxes: List[List[int]],
) -> float:
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


def _has_meaningful_value(value: Any) -> bool:
    return value is not None and bool(str(value).strip())


def _card_confidence(fields: Dict[str, Any], field_conf: Dict[str, float]) -> float:
    if not field_conf:
        return 0.0

    weighted_total = 0.0
    weight_sum = 0.0
    populated_core = 0

    for key, weight in _CORE_CONFIDENCE_WEIGHTS.items():
        value = fields.get(key)
        if not _has_meaningful_value(value):
            continue
        weighted_total += max(0.0, min(1.0, float(field_conf.get(key, 0.0)))) * weight
        weight_sum += weight
        populated_core += 1

    if weight_sum <= 0:
        return 0.0

    score = weighted_total / weight_sum

    if not _has_meaningful_value(fields.get("owner_name")):
        score -= 0.12
    if not _has_meaningful_value(fields.get("date_of_death")) and not _has_meaningful_value(fields.get("date_of_burial")):
        score -= 0.10
    if not _has_meaningful_value(fields.get("description")):
        score -= 0.06
    if populated_core < 4:
        score -= 0.05

    return max(0.0, min(1.0, score))


def _avg_word_confidence(words: List[Dict[str, Any]]) -> float:
    if not words:
        return 0.0
    confs = [_word_conf(w) for w in words]
    return sum(confs) / len(confs)


def _populated_field_count(parsed: Dict[str, Dict[str, Any]]) -> int:
    count = 0
    for value in parsed.values():
        field_value = value.get("value")
        if field_value is not None and str(field_value).strip():
            count += 1
    return count


def _label_hit_count(raw_text: str) -> int:
    if not raw_text.strip():
        return 0
    hits = 0
    for pattern in (
        r"\bdate\s+of\s+death\b",
        r"\bdate\s+of\s+burial\b",
        r"\bundertaker\b",
        r"\bsvc\s+no\b",
        r"\btype\s+of\s+grave\b",
        r"\bdescription\b",
        r"\bsex\b",
        r"\bage\b",
        r"\blot\b",
        r"\bsection\b",
        r"\bblock\b",
    ):
        if re.search(pattern, raw_text, re.IGNORECASE):
            hits += 1
    return hits


def _template_order_score(raw_text: str) -> float:
    if not raw_text.strip():
        return 0.0

    lines = [ln.strip().lower() for ln in raw_text.splitlines() if ln.strip()]
    if not lines:
        return 0.0

    def _find_idx(pattern: str) -> int | None:
        rx = re.compile(pattern, re.IGNORECASE)
        for idx, line in enumerate(lines):
            if rx.search(line):
                return idx
        return None

    score = 0.0

    first_line = lines[0]
    if "," in first_line and "date of" not in first_line and "description" not in first_line:
        score += 0.08

    death_idx = _find_idx(r"\bdate\s+of\s+death\b")
    burial_idx = _find_idx(r"\bdate\s+of\s+burial\b")
    description_idx = _find_idx(r"\bdescription\b")
    sex_idx = _find_idx(r"\bsex\b")
    age_idx = _find_idx(r"\bage\b")
    undertaker_idx = _find_idx(r"\bundertaker\b")
    svc_idx = _find_idx(r"\bsvc(?:\s+no)?\b")

    if death_idx is not None and burial_idx is not None:
        score += 0.12 if death_idx <= burial_idx else -0.12

    if burial_idx is not None and description_idx is not None:
        score += 0.06 if burial_idx <= description_idx else -0.06

    if description_idx is not None and sex_idx is not None:
        score += 0.08 if description_idx <= sex_idx else -0.08

    if sex_idx is not None and age_idx is not None:
        score += 0.05 if sex_idx <= age_idx else -0.05

    if age_idx is not None and undertaker_idx is not None:
        score += 0.05 if age_idx <= undertaker_idx else -0.05

    if undertaker_idx is not None and svc_idx is not None:
        score += 0.04 if undertaker_idx <= svc_idx else -0.04

    return score


def _orientation_score(
    parsed: Dict[str, Dict[str, Any]],
    words: List[Dict[str, Any]],
    raw_text: str,
    meta: Dict[str, Any],
) -> float:
    word_score = _avg_word_confidence(words)
    if word_score > 0:
        return word_score

    card_confidence = 0.0
    try:
        card_confidence = float(meta.get("card_confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        card_confidence = 0.0

    populated = _populated_field_count(parsed)
    label_hits = _label_hit_count(raw_text)
    template_order = _template_order_score(raw_text)
    raw_length_score = min(len(raw_text.strip()), 300) / 3000.0
    return card_confidence + (populated * 0.03) + (label_hits * 0.01) + template_order + raw_length_score


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


def _merge_missing_fields(
    parsed: Dict[str, Dict[str, Any]],
    fallback_fields: Dict[str, Any],
    raw_text: str,
) -> Dict[str, Dict[str, Any]]:
    merged = {k: {"value": v.get("value"), "support": list(v.get("support", []) or [])} for k, v in parsed.items()}
    for key, value in fallback_fields.items():
        if key not in merged:
            continue
        if not _is_reasonable_fallback_value(key, value, raw_text):
            continue
        current = merged[key].get("value")
        if current is None or str(current).strip() == "":
            merged[key]["value"] = value
    return merged


def _is_reasonable_fallback_value(key: str, value: Any, raw_text: str) -> bool:
    if value is None:
        return False

    text = str(value).strip()
    if not text:
        return False

    if key in {"date_of_death", "date_of_burial"}:
        # Let the local parser own date extraction; it's more conservative and
        # label-aware than the structured fallback.
        return False

    date_like = bool(re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text)) or bool(
        re.fullmatch(r"[A-Za-z]+\s+\d{1,2},\s*\d{2,4}", text)
    )

    if key in {"owner_address", "care_of", "relation"} and (date_like or _looks_like_labelish_value(text)):
        return False
    if key == "type_of_grave" and text.lower().startswith("description"):
        return False
    if key == "undertaker" and _looks_like_labelish_value(text):
        return False
    if key == "board_of_health_no" and not re.search(r"[0-9A-Za-z]", text):
        return False
    if key == "owner_address" and len(text) < 8:
        return False
    return True


def _looks_like_labelish_value(text: str) -> bool:
    lower = text.lower()
    return any(
        token in lower
        for token in (
            "date of",
            "description",
            "undertaker",
            "grave fee",
            "type of grave",
            "relation",
            "owner",
        )
    )


def _heuristic_field_confidence(key: str, value: Any, base_confidence: float) -> float:
    text = str(value).strip() if value is not None else ""
    if not text:
        return 0.0

    capped = min(float(base_confidence), 0.72)
    if key in {"owner_name", "date_of_death", "date_of_burial"}:
        capped = min(float(base_confidence), 0.82)
    elif key in {"undertaker", "grave_type", "board_of_health_no", "svc_no"}:
        capped = min(float(base_confidence), 0.68)
    elif key in {"owner_address", "care_of", "relation", "phone"}:
        capped = min(float(base_confidence), 0.60)

    if _looks_like_labelish_value(text):
        capped = min(capped, 0.25)
    return max(0.0, min(1.0, capped))


def _rotation_candidates() -> List[Tuple[int, Any]]:
    if get_ocr_engine_name() != "gemini":
        return _ORIENTATIONS

    rotation_mode = (
        str(get_config().get("ocr", {}).get("gemini", {}).get("rotation_mode", "sideways")).strip().lower()
    )
    if rotation_mode == "all":
        return _ORIENTATIONS
    if rotation_mode == "none":
        return [(0, None)]
    return _SIDEWAYS_ORIENTATIONS


def _ocr_pipeline(
    img: np.ndarray,
    *,
    use_structured_fallback: bool = True,
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], str, Dict[str, Any]]:
    pre = preprocess_array(img)
    ocr = run_ocr(pre)
    words = ocr.get("words", []) or []
    raw_text = ocr.get("raw_text", "") or ""
    parsed = ocr.get("fields") or parse_fields_min(words, raw_text=raw_text)
    parsed = _normalize_parsed_fields(parsed)

    if use_structured_fallback and get_ocr_engine_name() == "gemini" and raw_text:
        try:
            fallback_fields = parse_structured_fields_with_gemini(raw_text)
        except Exception:
            fallback_fields = {}
        if fallback_fields:
            parsed = _merge_missing_fields(parsed, fallback_fields, raw_text)

    meta = {
        "card_confidence": float(ocr.get("card_confidence", 0.0) or 0.0),
        "field_confidence": ocr.get("field_confidence") or {},
    }
    return parsed, words, raw_text, meta


def _build_result(
    parsed: Dict[str, Dict[str, Any]],
    words: List[Dict[str, Any]],
    raw_text: str,
    orientation: int,
    *,
    field_conf_override: Optional[Dict[str, Any]] = None,
    card_conf_override: Optional[float] = None,
) -> Dict[str, Any]:
    fields = {k: parsed[k]["value"] for k in parsed}
    field_support = {k: parsed[k]["support"] for k in parsed}
    field_confidence: Dict[str, float] = {
        k: _confidence_for_support(words, field_support[k]) for k in parsed
    }

    for k, v in (field_conf_override or {}).items():
        if k in field_confidence:
            try:
                field_confidence[k] = max(0.0, min(1.0, float(v)))
            except (TypeError, ValueError):
                pass

    for k in fields:
        if fields[k] is None or str(fields[k]).strip() == "":
            field_confidence[k] = 0.0
            field_support[k] = []
        elif (not field_support[k]) and card_conf_override is not None and k not in (field_conf_override or {}):
            try:
                field_confidence[k] = _heuristic_field_confidence(k, fields[k], float(card_conf_override))
            except (TypeError, ValueError):
                pass

    if card_conf_override is None:
        card_confidence = _card_confidence(fields, field_confidence)
    else:
        card_confidence = _card_confidence(fields, field_confidence)

    return {
        "fields": fields,
        "field_support": field_support,
        "field_confidence": field_confidence,
        "card_confidence": card_confidence,
        "raw_text": raw_text,
        "orientation": orientation,
        "meta": {
            "ocr_engine_version": get_ocr_engine_version(),
        },
    }


def process_card_min(image_path: str) -> Dict[str, Any]:
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    if not uses_rotation_sweep():
        parsed, words, raw_text, meta = _ocr_pipeline(img)
        return _build_result(
            parsed,
            words,
            raw_text,
            orientation=0,
            field_conf_override=meta.get("field_confidence"),
            card_conf_override=meta.get("card_confidence"),
        )

    best_conf = -1.0
    best_result: Tuple[Dict[str, Dict[str, Any]], List, str, int, Dict[str, Any]] | None = None

    for degree, rotate_flag in _rotation_candidates():
        rotated = img if rotate_flag is None else cv2.rotate(img, rotate_flag)
        parsed, words, raw_text, meta = _ocr_pipeline(rotated, use_structured_fallback=False)
        conf = _orientation_score(parsed, words, raw_text, meta)

        if conf > best_conf:
            best_conf = conf
            best_result = (parsed, words, raw_text, degree, meta)

    parsed, words, raw_text, degree, meta = best_result  # type: ignore[misc]

    if get_ocr_engine_name() == "gemini" and raw_text:
        try:
            fallback_fields = parse_structured_fields_with_gemini(raw_text)
        except Exception:
            fallback_fields = {}
        if fallback_fields:
            parsed = _merge_missing_fields(parsed, fallback_fields, raw_text)

    if degree != 0:
        logger.info(
            "Card %s: %d degrees selected (conf %.3f)",
            image_path,
            degree,
            best_conf,
        )

    return _build_result(
        parsed,
        words,
        raw_text,
        orientation=degree,
        field_conf_override=meta.get("field_confidence"),
        card_conf_override=meta.get("card_confidence"),
    )
