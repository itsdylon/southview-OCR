# parser.py
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# -------------------------
# basic helpers
# -------------------------
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


def _page_width(words: List[Dict[str, Any]]) -> int:
    return max((w["bbox"][2] for w in words), default=0)


def _find_word(words: List[Dict[str, Any]], pattern: str) -> Optional[Dict[str, Any]]:
    """
    Match pattern against:
      - raw text
      - normalized text (spaces collapsed)
      - alnum-normalized text (non-alnum -> space), which fixes tokens like Sex_M___, Fe$, etc.
    """
    rx = re.compile(pattern, re.IGNORECASE)
    for w in words:
        raw = str(w.get("text", "")).strip()
        if not raw:
            continue

        n1 = _norm(raw)
        n2 = re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip()

        if (
            rx.fullmatch(raw)
            or rx.search(raw)
            or rx.fullmatch(n1)
            or rx.search(n1)
            or rx.fullmatch(n2)
            or rx.search(n2)
        ):
            return w
    return None

from datetime import datetime

def _normalize_date(value: Optional[str]) -> Optional[str]:
    """
    Convert various date formats to ISO format: YYYY-MM-DD
    Handles:
        6/27/1966
        December 14, 2004
        3-20-94
    """
    if not value:
        return None

    value = value.strip()

    formats = [
        "%m/%d/%Y",
        "%m/%d/%y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%m-%d-%Y",
        "%m-%d-%y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return value  # fallback if unparseable

def _words_in_y_band(words: List[Dict[str, Any]], y0: int, y1: int) -> List[Dict[str, Any]]:
    out = []
    for w in words:
        _, wy0, _, wy1 = w["bbox"]
        if wy1 < y0 or wy0 > y1:
            continue
        if str(w.get("text", "")).strip():
            out.append(w)
    out.sort(key=lambda w: w["bbox"][0])
    return out


def _words_in_band_right_of(
    words: List[Dict[str, Any]],
    anchor: Dict[str, Any],
    *,
    x_pad: int = 6,
    y_tol: int = 10,
    x_max: Optional[int] = None,
) -> List[Dict[str, Any]]:
    ax1, ay1, ax2, ay2 = anchor["bbox"]
    y0 = ay1 - y_tol
    y1 = ay2 + y_tol
    xmin = ax2 + x_pad
    xmax = x_max if x_max is not None else 10**9

    cand = []
    for w in words:
        x1, y1w, x2, y2w = w["bbox"]
        if x1 < xmin or x1 > xmax:
            continue
        if y2w < y0 or y1w > y1:
            continue
        if not str(w.get("text", "")).strip():
            continue
        cand.append(w)

    cand.sort(key=lambda w: w["bbox"][0])
    return cand


def _join(ws: List[Dict[str, Any]]) -> str:
    return " ".join(w["text"] for w in ws).strip()


def _group_words_into_lines(words: List[Dict[str, Any]], *, y_tol: int = 10) -> List[List[Dict[str, Any]]]:
    ws = [w for w in words if str(w.get("text", "")).strip()]
    if not ws:
        return []

    ws.sort(key=lambda w: (w["bbox"][1], w["bbox"][0]))

    lines: List[List[Dict[str, Any]]] = []
    line_y: List[float] = []

    for w in ws:
        x1, y1, x2, y2 = w["bbox"]
        yc = (y1 + y2) / 2.0

        placed = False
        for i in range(len(lines)):
            if abs(yc - line_y[i]) <= y_tol:
                lines[i].append(w)
                line_y[i] = (line_y[i] * (len(lines[i]) - 1) + yc) / len(lines[i])
                placed = True
                break

        if not placed:
            lines.append([w])
            line_y.append(yc)

    for ln in lines:
        ln.sort(key=lambda w: w["bbox"][0])

    def _line_yc(ln: List[Dict[str, Any]]) -> float:
        return sum((w["bbox"][1] + w["bbox"][3]) / 2.0 for w in ln) / len(ln)

    lines.sort(key=_line_yc)
    return lines


def _lines_text(lines: List[List[Dict[str, Any]]]) -> List[str]:
    return [" ".join(w["text"] for w in ln).strip() for ln in lines if ln]


# -------------------------
# extractors
# -------------------------
def _extract_phone_anywhere(text: str) -> Optional[str]:
    m = re.search(r"(\(?\d{3}\)?\s*[-.]?\s*\d{3}\s*[-.]?\s*\d{4})", text)
    return m.group(1) if m else None


def _extract_date(text: str) -> Optional[str]:
    m = re.search(r"([A-Za-z]+ \d{1,2}, \d{4})", text)
    if m:
        return m.group(1)
    m = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", text)
    if m:
        return m.group(1)
    m = re.search(r"(\d{1,2}-\d{1,2}-\d{2,4})", text)
    return m.group(1) if m else None


def _cleanup_hyphen_date(s: str) -> str:
    x = re.sub(r"[^0-9\-]", "", s)
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{2,4})", x)
    if not m:
        return s
    mm, dd, yy = m.group(1), m.group(2), m.group(3)
    if len(yy) == 4:
        yy = yy[-2:]
    return f"{int(mm)}-{int(dd)}-{yy}"


def _split_city_state(s: str) -> tuple[Optional[str], Optional[str]]:
    s = s.strip()
    m = re.search(r"([A-Za-z .'-]+),\s*([A-Z]{2})\.?$", s)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.search(r"\b([A-Z]{2})\.?$", s)
    if m:
        return None, m.group(1).strip()
    return None, None


def _cleanup_address_city(addr: Optional[str], city_state: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    if not addr:
        return None, None, None

    a = addr.strip()
    m = re.search(r"^(.*)\s+([A-Za-z .'-]+),$", a)
    if m:
        street = m.group(1).strip()
        city = m.group(2).strip()
        cs = (city_state or "").strip()
        _, st = _split_city_state(cs) if cs else (None, None)
        return street or None, city or None, st

    city, st = _split_city_state(city_state or "")
    return a or None, city, st


def _find_words(words: List[Dict[str, Any]], pattern: str) -> List[Dict[str, Any]]:
    rx = re.compile(pattern, re.IGNORECASE)
    out = []
    for w in words:
        t = _norm(w.get("text", ""))
        if rx.fullmatch(t) or rx.search(t):
            out.append(w)
    return out


def _pick_svc_no_anchor(words: List[Dict[str, Any]], W: int) -> Optional[Dict[str, Any]]:
    svcs = _find_words(words, r"\bsvc\b")
    if not svcs:
        return None

    left_svcs = [w for w in svcs if w["bbox"][0] < int(W * 0.45)]
    candidates = left_svcs or svcs

    best = None
    best_score = -10**9

    for s in candidates:
        x1, y1, x2, y2 = s["bbox"]
        line_ws = _words_in_y_band(words, y1 - 16, y2 + 16)
        line_txt = _join(line_ws)

        score = 0
        if re.search(r"\bN[O0]\b", line_txt, re.IGNORECASE):
            score += 100
        score += int((y1 + y2) / 2)
        score += int((W - x1))

        if score > best_score:
            best_score = score
            best = s

    return best


def _top_header_regions(words: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not words:
        return None, None, None

    W = _page_width(words)
    if W <= 0:
        return None, None, None

    top_band = sorted(words, key=lambda w: w["bbox"][1])
    top_y = top_band[0]["bbox"][1]
    header_words = [w for w in words if w["bbox"][1] <= top_y + 40]
    header_words.sort(key=lambda w: w["bbox"][0])

    left = [w for w in header_words if w["bbox"][0] < W * 0.38]
    mid = [w for w in header_words if W * 0.38 <= w["bbox"][0] < W * 0.78]
    right = [w for w in header_words if w["bbox"][0] >= W * 0.78]

    return _join(left) or None, _join(mid) or None, _join(right) or None


def _clean_single_word(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    parts = s.strip().split()
    return parts[0] if parts else None


def _extract_money(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.replace("O", "0").replace("o", "0")
    m = re.search(r"\$?\s*([0-9]{2,4})\s*([.\-])\s*([0-9]{2})\b", t)
    if m:
        return f"{m.group(1)}.{m.group(3)}"
    m = re.search(r"\$\s*([0-9]{2,4})\b", t)
    if m:
        return m.group(1)
    return None


# -------------------------
# template-variant helpers
# -------------------------
def parse_compact_description_line(text: str) -> Dict[str, Optional[str]]:
    """
    Handles formats like:
      "Description: Lot #64~- Range G- Grave 9- Section 2~ Block @ SS"
    """
    if not text:
        return {"lot_no": None, "range": None, "grave_no": None, "section_no": None, "block_side": None}

    t = text
    t = t.replace("~", " ")
    t = re.sub(r"[_]+", " ", t)
    t = re.sub(r"\s*-\s*", " - ", t)
    t = re.sub(r"\s+", " ", t).strip()

    out = {"lot_no": None, "range": None, "grave_no": None, "section_no": None, "block_side": None}

    m = re.search(r"\bLot\b\s*#?\s*([0-9]{1,4})\b", t, re.IGNORECASE)
    if m:
        out["lot_no"] = m.group(1)

    m = re.search(r"\bRange\b\s*([A-Za-z0-9]{1,3})\b", t, re.IGNORECASE)
    if m:
        out["range"] = m.group(1)

    m = re.search(r"\bGrave\b\s*#?\s*([0-9]{1,4})\b", t, re.IGNORECASE)
    if m:
        out["grave_no"] = m.group(1)

    m = re.search(r"\bSection\b\s*#?\s*([0-9]{1,3})\b", t, re.IGNORECASE)
    if m:
        out["section_no"] = m.group(1)

    m = re.search(r"\bBlock\b\s*#?\s*([0-9@]{1,3})\s*([A-Za-z]{1,12})?\b", t, re.IGNORECASE)
    if m:
        blk_raw = m.group(1)
        blk = blk_raw.replace("@", "2")  # template-specific OCR fix (common for this dataset)
        side = (m.group(2) or "").strip()
        out["block_side"] = f"Block {blk} {side}".strip()

    return out


# -------------------------
# bottom row (layout-based)
# -------------------------
def parse_sex_age_type_fee_from_layout(words: List[Dict[str, Any]], W: int):
    sex = age = type_of_grave = grave_fee = None

    sex_anchor = _find_word(words, r"\bsex\b")
    if not sex_anchor:
        sex_anchor = _find_word(words, r"\bage\b") or _find_word(words, r"\btype\b") or _find_word(words, r"\bfe\b|\bfee\b")

    if not sex_anchor:
        return None, None, None, None, []

    y1 = sex_anchor["bbox"][1]
    y2 = sex_anchor["bbox"][3]

    row_ws = _words_in_y_band(words, y1 - 25, y2 + 25)
    row_txt = _join(row_ws)

    norm = re.sub(r"[^a-zA-Z0-9]+", " ", row_txt).strip()
    norm = re.sub(r"\s+", " ", norm)

    m = re.search(r"\bsex\s*([MF])\b", norm, flags=re.IGNORECASE)
    if m:
        sex = m.group(1).upper()

    m = re.search(r"\bage\s*(\d{1,3})\b", norm, flags=re.IGNORECASE)
    if m:
        age = m.group(1)

    def _toknorm(t: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", t.lower())

    grave_i = None
    fee_i = None

    for i, w in enumerate(row_ws):
        t = _toknorm(w["text"])
        if grave_i is None and t == "grave":
            grave_i = i
        if fee_i is None and (t == "fee" or w["text"].lower().strip() in {"fe$", "fee"}):
            fee_i = i

    if grave_i is not None:
        start = grave_i + 1
        end = fee_i if (fee_i is not None and fee_i > start) else len(row_ws)
        cand = row_ws[start:end]

        junk = {"(2", "hoy", "on)", "on", "2"}
        cleaned = [w for w in cand if _toknorm(w["text"]) not in junk]

        parts = _join(cleaned).split()
        # Only accept if it looks like a real value (not just label bleed)
        if parts and " ".join(parts[:2]).lower() not in {"grave", "type"}:
            type_of_grave = " ".join(parts[:2]) if parts else None

    grave_fee = _extract_money(row_txt)
    return sex, age, type_of_grave, grave_fee, row_ws


# -------------------------
# SVC No
# -------------------------
def _svc_digits_fix(s: str) -> str:
    return s.replace("O", "0").replace("o", "0").replace("G", "8").replace("I", "1").replace("l", "1")


def parse_svc_no_from_layout(words: List[Dict[str, Any]], W: int) -> Optional[str]:
    svc_anchor = _pick_svc_no_anchor(words, W)
    if not svc_anchor:
        return None

    y1 = svc_anchor["bbox"][1]
    y2 = svc_anchor["bbox"][3]
    line = _join(_words_in_y_band(words, y1 - 18, y2 + 18))

    m = re.search(r"\b([0-9]{1,3}(?:,[0-9]{3})+)\b", line)
    if m:
        return m.group(1)

    m = re.search(r"\b([0-9]{4,7})\b", line)
    if m:
        return m.group(1)

    cand = _words_in_band_right_of(words, svc_anchor, x_pad=6, y_tol=20, x_max=int(W * 0.60))
    cand_text = _join(cand)
    m = re.search(r"\b([0-9]{1,3}(?:,[0-9]{3})+)\b", cand_text) or re.search(r"\b([0-9]{4,7})\b", cand_text)
    return m.group(1) if m else None


def parse_svc_no_from_text(all_text: str) -> Optional[str]:
    for ln in all_text.splitlines():
        if not re.search(r"\bSVC\b", ln, flags=re.IGNORECASE):
            continue

        # comma numbers
        m = re.search(r"\b([0-9]{1,3}(?:,[0-9]{3})+)\b", ln)
        if m:
            return m.group(1)

        # allow OCR letters in digits (e.g., GO47 -> 8047)
        m = re.search(r"\b([0-9GOIl]{4,7})\b", ln)
        if m:
            cand = _svc_digits_fix(m.group(1))
            cand = re.sub(r"\D", "", cand)
            if 4 <= len(cand) <= 7:
                return cand

    return None


# -------------------------
# text-line bottom row parser (kept, but layout fallback is primary)
# -------------------------
def parse_sex_age_type_fee_from_text(all_text: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    line = None
    for ln in all_text.splitlines():
        if re.search(r"\bSex\b", ln, flags=re.IGNORECASE) and re.search(r"\bAge\b", ln, flags=re.IGNORECASE):
            line = ln
            break
    if not line:
        return None, None, None, None

    norm = re.sub(r"[_]+", " ", line)
    norm = re.sub(r"\s+", " ", norm).strip()

    sex = None
    m = re.search(r"\bSex\b\s*([MF])\b", norm, flags=re.IGNORECASE)
    if m:
        sex = m.group(1).upper()

    age = None
    m = re.search(r"\bAge\b\s*(\d{1,3})\b", norm, flags=re.IGNORECASE)
    if m:
        age = m.group(1)

    type_of_grave = None
    m = re.search(r"\bType\s+of\s+Grave\b\s*(.*?)(?=\bGrave\s*Fee\b|$)", norm, flags=re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        parts = val.split()
        # if empty or looks like label bleed, treat as None
        if parts and " ".join(parts[:2]).lower() not in {"grave", "type"}:
            type_of_grave = " ".join(parts[:4])

    grave_fee = None
    m = re.search(r"\bGrave\s*F\w*\$?\s*([0-9]{2,4})\s*[-.]\s*([0-9]{2})\b", norm, flags=re.IGNORECASE)
    if m:
        grave_fee = f"{m.group(1)}.{m.group(2)}"
    else:
        m = re.search(r"\$\s*([0-9]{2,4})", norm)
        if m:
            grave_fee = m.group(1)

    return sex, age, type_of_grave, grave_fee


def _support_from_words(ws: List[Dict[str, Any]]) -> List[List[int]]:
    return [w["bbox"] for w in (ws or []) if isinstance(w, dict) and "bbox" in w]


def _wrap(value: Optional[str], support_words: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {"value": value, "support": _support_from_words(support_words)}


def _repair_compact_hyphen_date(s: str) -> Optional[str]:
    """
    Repairs OCR like:
      '35-2094)' -> '3-20-94' (or '3-20-41' depending on last two digits)
    Strategy:
      - strip non-digits/hyphens
      - if pattern is 'DD-DDDD' (e.g. 35-2094), interpret as M D - DD YY
        => 3-20-94
    """
    if not s:
        return None

    x = re.sub(r"[^0-9\-]", "", s)
    x = re.sub(r"-{2,}", "-", x).strip("-")

    # already normal
    if re.fullmatch(r"\d{1,2}-\d{1,2}-\d{2,4}", x):
        return _cleanup_hyphen_date(x)

    # compact: 35-2094 => 3-20-94
    m = re.fullmatch(r"(\d{2})-(\d{4})", x)
    if m:
        a = m.group(1)   # '35'
        b = m.group(2)   # '2094'
        mm = a[0]        # '3'
        dd = a[1] + b[0] # '5' + '2' => '52' (too big, so use alternative below)

        # better split: M | DD from first 3 digits of second group
        # 35-2094 => M=3, DD=20, YY=94
        mm = a[0]
        dd = b[:2]
        yy = b[2:]

        try:
            mm_i = int(mm)
            dd_i = int(dd)
        except ValueError:
            return None

        if 1 <= mm_i <= 12 and 1 <= dd_i <= 31:
            return f"{mm_i}-{dd_i}-{yy}"

    return None

# -------------------------
# main entry
# -------------------------
def parse_fields(words: List[Dict[str, Any]]) -> Dict[str, Any]:
    W = _page_width(words)

    lines = _group_words_into_lines(words, y_tol=10)
    line_texts = _lines_text(lines)

    all_text = "\n".join(line_texts)
    all_text_flat = " ".join(line_texts)

    # -------- Header fields --------
    owner_name, owner_address_raw, owner_city_state_raw = _top_header_regions(words)

    header_ws = []
    if words:
        top_y = min(w["bbox"][1] for w in words)
        header_ws = [w for w in words if w["bbox"][1] <= top_y + 40]
        header_ws.sort(key=lambda w: w["bbox"][0])

    left_ws = [w for w in header_ws if w["bbox"][0] < W * 0.38]
    mid_ws = [w for w in header_ws if W * 0.38 <= w["bbox"][0] < W * 0.78]
    right_ws = [w for w in header_ws if w["bbox"][0] >= W * 0.78]

    owner_city, owner_state = _split_city_state(owner_city_state_raw or "")
    owner_address, owner_city2, owner_state2 = _cleanup_address_city(owner_address_raw, owner_city_state_raw)
    if owner_city2:
        owner_city = owner_city2
    if owner_state2:
        owner_state = owner_state2

    # -------- care_of --------
    care_of = None
    care_of_ws: List[Dict[str, Any]] = []
    estate = _find_word(words, r"\bestate\b")
    if estate:
        care_of_ws = _words_in_band_right_of(words, estate, y_tol=12, x_pad=8, x_max=W)
        care_of = _join(care_of_ws) or None

    # -------- phone --------
    phone = _extract_phone_anywhere(all_text_flat)

    # -------- dates --------
    date_of_death = None
    dod_ws: List[Dict[str, Any]] = []
    dod_anchor = _find_word(words, r"\bdeath\b")
    if dod_anchor:
        dod_ws = _words_in_band_right_of(words, dod_anchor, y_tol=14, x_pad=8, x_max=int(W * 0.60))
        dod_text = _join(dod_ws)
        date_of_death = _extract_date(dod_text)
        if date_of_death and "-" in date_of_death:
            date_of_death = _cleanup_hyphen_date(date_of_death)

    date_of_burial = None
    bur_ws: List[Dict[str, Any]] = []
    burial_anchor = _find_word(words, r"\bburial\b")
    if burial_anchor:
        # Wider y_tol helps this template
        bur_ws = _words_in_band_right_of(words, burial_anchor, y_tol=24, x_pad=8, x_max=W)
        bur_text = _join(bur_ws)

        date_of_burial = _extract_date(bur_text)
        if date_of_burial and "-" in date_of_burial:
            date_of_burial = _cleanup_hyphen_date(date_of_burial)

        if date_of_burial is None:
            # Try repairing compact OCR like 35-2094)
            repaired = _repair_compact_hyphen_date(bur_text)
            if repaired:
                date_of_burial = repaired

    date_of_birth = None
    dob_ws: List[Dict[str, Any]] = []
    dob_anchor = _find_word(words, r"\bdob\b")
    if dob_anchor:
        dob_ws = _words_in_band_right_of(words, dob_anchor, y_tol=14, x_pad=8)
        dob_text = _join(dob_ws)
        date_of_birth = _extract_date(dob_text) or (dob_text or None)

    # -------- LOT / Range / Grave --------
    lot_no = range_val = grave_no = None
    lot_line_ws: List[Dict[str, Any]] = []
    lot_anchor = _find_word(words, r"\blot#\b|\blot\b")
    if lot_anchor:
        _, ay1, _, _ = lot_anchor["bbox"]
        lot_line_ws = _words_in_y_band(words, ay1 - 18, ay1 + 18)
        line = _join(lot_line_ws)

        m = re.search(r"LOT#\s*([0-9]+)", line, flags=re.IGNORECASE)
        if m:
            lot_no = m.group(1)
        m = re.search(r"\bRange\s*([A-Za-z0-9]+)\b", line, flags=re.IGNORECASE)
        if m:
            range_val = m.group(1)
        m = re.search(r"Grave#\s*([0-9]+)", line, flags=re.IGNORECASE)
        if m:
            grave_no = m.group(1)

    # -------- Section / Block Side --------
    section_no = None
    block_side = None
    sec_line_ws: List[Dict[str, Any]] = []
    sec_anchor = _find_word(words, r"\bsection\b")
    if sec_anchor:
        _, ay1, _, _ = sec_anchor["bbox"]
        sec_line_ws = _words_in_y_band(words, ay1 - 18, ay1 + 18)
        line = _join(sec_line_ws)

        m = re.search(r"\bSection\s*([0-9]+)", line, flags=re.IGNORECASE)
        if m:
            section_no = m.group(1)
        m = re.search(r"\bSection\s*[0-9]+\s*(.*)$", line, flags=re.IGNORECASE)
        if m:
            block_side = m.group(1).strip() or None

    # ---- Compact Description fallback (template variant) ----
    if lot_no is None or range_val is None or grave_no is None or section_no is None or block_side is None:
        desc_anchor = _find_word(words, r"\bdescription\b")
        if desc_anchor:
            y1 = desc_anchor["bbox"][1]
            y2 = desc_anchor["bbox"][3]
            desc_ws = _words_in_y_band(words, y1 - 18, y2 + 28)
            desc_text = _join(desc_ws)

            comp = parse_compact_description_line(desc_text)
            lot_no = lot_no or comp["lot_no"]
            range_val = range_val or comp["range"]
            grave_no = grave_no or comp["grave_no"]
            section_no = section_no or comp["section_no"]
            block_side = block_side or comp["block_side"]

            if not lot_line_ws:
                lot_line_ws = desc_ws
            if not sec_line_ws:
                sec_line_ws = desc_ws

    # -------- Sex / Age / Type / Grave Fee --------
    sex, age, type_of_grave, grave_fee = parse_sex_age_type_fee_from_text(all_text)

    bottom_support: List[Dict[str, Any]] = []
    if sex is None or age is None or type_of_grave is None or grave_fee is None:
        s2, a2, t2, g2, row_ws = parse_sex_age_type_fee_from_layout(words, W)
        sex = sex or s2
        age = age or a2
        type_of_grave = type_of_grave or t2
        grave_fee = grave_fee or g2
        bottom_support = row_ws

    # -------- Undertaker --------
    undertaker = None
    und_ws: List[Dict[str, Any]] = []
    und_anchor = _find_word(words, r"\bundertaker\b")
    if und_anchor:
        und_ws = _words_in_band_right_of(words, und_anchor, y_tol=10, x_pad=8, x_max=int(W * 0.60))
        undertaker = _clean_single_word(_join(und_ws))

    # -------- SVC No --------
    svc_no = parse_svc_no_from_text(all_text)
    if svc_no is None:
        svc_no = parse_svc_no_from_layout(words, W)

    
    date_of_birth = _normalize_date(date_of_birth)
    date_of_death = _normalize_date(date_of_death)
    date_of_burial = _normalize_date(date_of_burial)

    return {
        "owner_name": _wrap(owner_name, left_ws),
        "owner_address": _wrap(owner_address, mid_ws),
        "owner_city": _wrap(owner_city, right_ws),
        "owner_state": _wrap(owner_state, right_ws),
        "care_of": _wrap(care_of, care_of_ws),
        "phone": _wrap(phone, []),
        "date_of_death": _wrap(date_of_death, dod_ws),
        "date_of_burial": _wrap(date_of_burial, bur_ws),
        "date_of_birth": _wrap(date_of_birth, dob_ws),
        "lot_no": _wrap(lot_no, lot_line_ws),
        "range": _wrap(range_val, lot_line_ws),
        "grave_no": _wrap(grave_no, lot_line_ws),
        "section_no": _wrap(section_no, sec_line_ws),
        "block_side": _wrap(block_side, sec_line_ws),
        "sex": _wrap(sex, bottom_support),
        "age": _wrap(age, bottom_support),
        "type_of_grave": _wrap(type_of_grave, bottom_support),
        "grave_fee": _wrap(grave_fee, bottom_support),
        "undertaker": _wrap(undertaker, und_ws),
        "svc_no": _wrap(svc_no, []),
    }