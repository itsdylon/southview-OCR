import math
from typing import Any, Dict, List, Optional, Tuple


def _word_conf(w: Dict[str, Any]) -> float:
    """
    Returns confidence as 0..1 float.
    Supports keys: 'confidence' or 'conf' (your wrapper has both).
    """
    c = w.get("confidence", None)
    if c is None:
        c = w.get("conf", None)
    if c is None:
        return 0.5
    c = float(c)
    return c / 100.0 if c > 1.0 else c


def _bbox_key(b: List[int]) -> Tuple[int, int, int, int]:
    return (int(b[0]), int(b[1]), int(b[2]), int(b[3]))


def build_bbox_index(words: List[Dict[str, Any]]) -> Dict[Tuple[int, int, int, int], Dict[str, Any]]:
    """
    Map bbox -> word dict for O(1) lookup when you only have support bboxes.
    Assumes bboxes are unique enough (works with your current output).
    """
    idx = {}
    for w in words:
        b = w.get("bbox")
        if not b:
            continue
        idx[_bbox_key(b)] = w
    return idx


def support_words_from_bboxes(
    support_bboxes: List[List[int]],
    bbox_index: Dict[Tuple[int, int, int, int], Dict[str, Any]],
) -> List[Dict[str, Any]]:
    out = []
    for b in support_bboxes or []:
        w = bbox_index.get(_bbox_key(b))
        if w is not None:
            out.append(w)
    return out


def score_field(
    value: Optional[str],
    support_words: List[Dict[str, Any]],
    *,
    expected: Optional[str] = None,
    fallback: bool = False,
) -> float:
    """
    Base: mean support confidence.
    Bonuses/Penalties:
      - regex match bonus
      - fallback penalty
      - short support penalty (weak evidence)
    """
    if not value or (isinstance(value, str) and not value.strip()):
        return 0.0

    if support_words:
        base = sum(_word_conf(w) for w in support_words) / len(support_words)
    else:
        base = 0.35  # no support => low default

    # weak evidence penalty
    if len(support_words) == 1:
        base -= 0.08
    elif len(support_words) == 2:
        base -= 0.04

    # expected-format adjustment
    if expected:
        import re
        if re.fullmatch(expected, value.strip()):
            base += 0.10
        else:
            base -= 0.20

    if fallback:
        base -= 0.05

    return float(max(0.0, min(1.0, base)))


FIELD_WEIGHTS: Dict[str, float] = {
    "owner_name": 0.10,
    "owner_address": 0.06,
    "owner_city": 0.04,
    "owner_state": 0.03,
    "care_of": 0.04,
    "phone": 0.06,
    "date_of_death": 0.08,
    "date_of_burial": 0.06,
    "date_of_birth": 0.06,
    "lot_no": 0.05,
    "range": 0.04,
    "grave_no": 0.05,
    "section_no": 0.05,
    "block_side": 0.04,
    "sex": 0.03,
    "age": 0.03,
    "type_of_grave": 0.05,
    "grave_fee": 0.06,
    "undertaker": 0.03,
    "svc_no": 0.08,
}


EXPECTED_PATTERNS: Dict[str, str] = {
    "phone": r"\(?\d{3}\)?\s*[-.]?\s*\d{3}\s*[-.]?\s*\d{4}",
    "sex": r"[MF]",
    "age": r"\d{1,3}",
    "grave_fee": r"\d{2,4}\.\d{2}",
    "lot_no": r"\d+",
    "grave_no": r"\d+",
    "section_no": r"\d+",
    "range": r"[A-Za-z0-9]+",
    "svc_no": r"\d{1,3}(?:,\d{3})+|\d{4,7}",
}


def weighted_card_conf(field_conf: Dict[str, float], weights: Dict[str, float]) -> float:
    num = 0.0
    den = 0.0
    for k, w in weights.items():
        if k in field_conf:
            den += w
            num += w * field_conf[k]
    return float(num / den) if den > 0 else 0.0

def add_confidence(parsed: Dict[str, Dict[str, Any]], ocr_words: List[Dict[str, Any]]) -> Dict[str, Any]:
    bbox_index = build_bbox_index(ocr_words)

    field_conf: Dict[str, float] = {}
    fields: Dict[str, Any] = {}
    field_support: Dict[str, List[List[int]]] = {}

    for field, obj in parsed.items():
        val = obj.get("value")
        support_bboxes = obj.get("support", []) or []
        support_words = support_words_from_bboxes(support_bboxes, bbox_index)

        fields[field] = val
        field_support[field] = support_bboxes

        expected = EXPECTED_PATTERNS.get(field)
        # You can thread through a real fallback flag later; default False for now.
        field_conf[field] = score_field(val, support_words, expected=expected, fallback=False)

    card_conf = weighted_card_conf(field_conf, FIELD_WEIGHTS)

    return {
        "fields": fields,
        "field_support": field_support,
        "field_confidence": field_conf,
        "card_confidence": card_conf,
    }