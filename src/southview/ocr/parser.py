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
def _split_header_name_address(line_texts: List[str]) -> Tuple[Optional[str], Optional[str]]:
    # take first non-empty line
    header = None
    for ln in line_texts:
        if ln.strip():
            header = ln.strip()
            break
    if not header:
        return None, None

    # find first street number token
    m = re.search(r"\b(\d{1,6})\b", header)
    if not m:
        return None, None

    idx = m.start()
    left = header[:idx].strip()
    right = header[idx:].strip()

    # remove common parentheses titles from name
    left = re.sub(r"\([^)]*\)", "", left).strip(" ,")

    # collapse weird zip spacing like "303 14" -> "30314"
    right = re.sub(r"\b(\d{3})\s+(\d{2})\b", r"\1\2", right)

    return (left or None), (right or None)


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

def _is_missing(v: Optional[str]) -> bool:
    return v is None or str(v).strip() == ""


def _parks_like(all_text: str) -> bool:
    t = all_text.lower()
    return ("contact information" in t) or ("sex:" in t) or ("date of death" in t)

# -------------------------
# extractors
# -------------------------
def _parse_description_and_section_block(line_texts: List[str]) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {
        "lot_no": None,
        "range": None,
        "grave_no": None,
        "section_no": None,
        "block_side": None,
    }

    # Find "Description:" line
    desc_i = None
    for i, ln in enumerate(line_texts):
        if re.search(r"\bdescription\b", ln, re.IGNORECASE):
            desc_i = i
            break

    if desc_i is not None:
        ln = line_texts[desc_i]
        # allow Grave/Gave
        m = re.search(r"\bLot\s*#?\s*([0-9]{1,4})\b", ln, re.IGNORECASE)
        if m:
            out["lot_no"] = m.group(1)
        m = re.search(r"\bRange\s*([A-Za-z0-9]{1,3})\b", ln, re.IGNORECASE)
        if m:
            out["range"] = m.group(1)
        m = re.search(r"\b(?:Grave|Gave)\s*#?\s*([0-9]{1,4})\b", ln, re.IGNORECASE)
        if m:
            out["grave_no"] = m.group(1)

        # section/block often on next line
        for k in (desc_i, desc_i + 1, desc_i + 2):
            if k >= len(line_texts):
                continue
            s = line_texts[k]

            ms = re.search(r"\bSection\s*#?\s*([0-9]{1,3})\b", s, re.IGNORECASE)
            if ms:
                out["section_no"] = ms.group(1)

            mb = re.search(r"\bBlock\s*#?\s*([0-9@]{1,3})\b", s, re.IGNORECASE)
            if mb:
                blk = mb.group(1).replace("@", "2")
                # optional side word
                side = None
                mside = re.search(r"\b(Northside|Southside|Eastside|Westside)\b", s, re.IGNORECASE)
                if mside:
                    side = mside.group(1).capitalize()
                out["block_side"] = f"Block {blk}" + (f" {side}" if side else "")

            # sometimes side appears as a trailing word without exact matches
            if out["block_side"] and ("Northside" not in out["block_side"]) and ("Southside" not in out["block_side"]):
                mtrail = re.search(r"\bBlock\s*[0-9@]{1,3}\s+([A-Za-z]{4,12})\b", s, re.IGNORECASE)
                if mtrail:
                    out["block_side"] = (out["block_side"] + " " + mtrail.group(1)).strip()

    return out

def _clean_ocr_date_noise(s: str) -> str:
    if not s:
        return s
    x = s.strip()

    # common OCR month typos
    x = re.sub(r"\bQctober\b", "October", x, flags=re.IGNORECASE)
    x = re.sub(r"\b0ctober\b", "October", x, flags=re.IGNORECASE)  # leading zero
    x = re.sub(r"\b0ct\b", "Oct", x, flags=re.IGNORECASE)

    # strip trailing junk like "202]"
    x = re.sub(r"[^\w\s,/-]+$", "", x)

    # Fix missing space after comma: ",2021" -> ", 2021"
    x = re.sub(r",\s*(\d{4})\b", r", \1", x)

    # collapse whitespace
    x = re.sub(r"\s+", " ", x).strip()
    return x

def _extract_two_dates_from_line(line: str) -> List[str]:
    """
    If a line contains two dates (common on PARKS template),
    return them in reading order.
    """
    if not line:
        return []
    line = _clean_ocr_date_noise(line)

    dates: List[str] = []
    # Month DD, YYYY
    for m in re.finditer(r"\b([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\b", line):
        dates.append(f"{m.group(1)} {int(m.group(2))}, {m.group(3)}")

    # numeric dates if no month dates found
    if not dates:
        for m in re.finditer(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", line):
            mm, dd, yy = m.group(1), m.group(2), m.group(3)
            if len(yy) == 2:
                dates.append(f"{int(mm)}/{int(dd)}/{yy}")
            else:
                dates.append(f"{int(mm)}/{int(dd)}/{yy}")

    return dates

def _extract_date_loose(text: str) -> Optional[str]:
    if not text:
        return None
    text = _clean_ocr_date_noise(text)

    # Month DD, YYYY (allow missing space after comma already fixed)
    m = re.search(r"\b([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\b", text)
    if m:
        return f"{m.group(1)} {int(m.group(2))}, {m.group(3)}"

    # M/D/YY(YY) or M-D-YY(YY)
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", text)
    if m:
        mm, dd, yy = m.group(1), m.group(2), m.group(3)
        if len(yy) == 2:
            return f"{int(mm)}/{int(dd)}/{yy}"
        return f"{int(mm)}/{int(dd)}/{yy}"

    # Hyphen short: 3-20-94
    m = re.search(r"\b(\d{1,2})-(\d{1,2})-(\d{2,4})\b", text)
    if m:
        mm, dd, yy = m.group(1), m.group(2), m.group(3)
        if len(yy) == 4:
            yy = yy[-2:]
        return f"{int(mm)}-{int(dd)}-{yy}"

    return None
def _find_near(words: List[Dict[str, Any]], pattern: str, *, y_center: int, y_tol: int = 30) -> Optional[Dict[str, Any]]:
    rx = re.compile(pattern, re.IGNORECASE)
    best = None
    best_dy = 10**9
    for w in words:
        t = str(w.get("text", "")).strip()
        if not t:
            continue
        if not (rx.search(t) or rx.search(_norm(t))):
            continue
        y1, y2 = w["bbox"][1], w["bbox"][3]
        yc = (y1 + y2) // 2
        dy = abs(yc - y_center)
        if dy <= y_tol and dy < best_dy:
            best_dy = dy
            best = w
    return best


def _parks_type_and_fee_from_words(words: List[Dict[str, Any]], W: int) -> Tuple[Optional[str], Optional[str]]:
    """
    For PARKS template: read type between 'Type' (or 'Type of') and 'Grave Fee',
    and read fee to the right of 'Grave Fee'.
    """
    if not words:
        return None, None

    # find a "Type" anchor that is in the lower half of page
    type_anchor = None
    for w in words:
        if w["bbox"][1] < int(0.55 * max(1, max(x["bbox"][3] for x in words))):
            continue
        if re.search(r"\btype\b", str(w.get("text", "")), re.IGNORECASE):
            type_anchor = w
            break

    if not type_anchor:
        # fallback: any "type" anywhere
        type_anchor = _find_word(words, r"\btype\b")

    if not type_anchor:
        return None, None

    y_center = (type_anchor["bbox"][1] + type_anchor["bbox"][3]) // 2

    # find "Fee" anchor on same row (often "Fee" or "Fec" or "Fe")
    fee_anchor = _find_near(words, r"\bfee\b|\bfec\b|\bfe\b", y_center=y_center, y_tol=40)
    if not fee_anchor:
        fee_anchor = _find_near(words, r"\bgrave\b", y_center=y_center, y_tol=40)  # weak fallback

    # TYPE: words right of "Type" until "Fee" (or until far right)
    x_max = fee_anchor["bbox"][0] if fee_anchor else W
    type_words = _words_in_band_right_of(words, type_anchor, x_pad=4, y_tol=30, x_max=int(x_max))
    type_txt = _join(type_words)
    type_txt = re.sub(r"\b(of|grave)\b", "", type_txt, flags=re.IGNORECASE).strip()
    # keep first 3 tokens to avoid spillover
    parts = type_txt.split()
    type_val = " ".join(parts[:3]) if parts else None

    # FEE: words right of fee anchor
    fee_val = None
    if fee_anchor:
        fee_words = _words_in_band_right_of(words, fee_anchor, x_pad=4, y_tol=40, x_max=W)
        fee_val = _extract_money(_join(fee_words))

    return type_val, fee_val


def _find_labelled_date(line_texts: List[str], label_rx: str) -> Optional[str]:
    rx = re.compile(label_rx, re.IGNORECASE)
    for i, ln in enumerate(line_texts):
        if not rx.search(ln):
            continue

        # same line
        d = _extract_date_loose(ln)
        if d:
            return d

        # next 2 lines
        for j in (i + 1, i + 2):
            if j < len(line_texts):
                d2 = _extract_date_loose(line_texts[j])
                if d2:
                    return d2
    return None
def _extract_phone_anywhere(text: str) -> Optional[str]:
    if not text:
        return None
    # Accept: (404) 784-2878, 404-784-2878, 404/784-2878, 404.784.2878, 404 784 2878
    m = re.search(r"(\(?\d{3}\)?\s*[-./]?\s*\d{3}\s*[-./]?\s*\d{4})", text)
    return m.group(1) if m else None


def _extract_date(text: str) -> Optional[str]:
    if not text:
        return None

    t = text

    # Common OCR fixes
    t = t.replace("Qctober", "October")
    t = t.replace("Oclober", "October")
    t = t.replace("0ctober", "October")

    # year OCR: 202] -> 2021, 2004] -> 20041 (but we only want last digit)
    t = re.sub(r"(\d{3})\]", r"\11", t)   # 202] -> 2021
    t = re.sub(r"(\d{3})\)", r"\11", t)   # 202) -> 2021 (sometimes)

    # normalize whitespace/underscores
    t = re.sub(r"[_]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    m = re.search(r"([A-Za-z]+\.?\s+\d{1,2},\s+\d{4})", t)
    if m:
        # Normalize "Oct." -> "Oct"
        return m.group(1).replace("  ", " ").strip()

    m = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", t)
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


def _top_header_regions(words: List[Dict[str, Any]], line_texts: Optional[List[str]] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (owner_name, owner_address_full).

    New logic:
      - Prefer parsing from the first OCR line if it contains a street number.
      - Otherwise fallback to old x-band split and return the mid-part as address.
    """
    # 1) Prefer first line parse (robust across templates)
    if line_texts:
        first = line_texts[0].strip()
        if first:
            # Normalize a bit
            first = re.sub(r"\s+", " ", first)

            # If there's a digit, treat it as start of address
            m = re.search(r"\b\d{1,6}\b", first)
            if m:
                owner_name = first[: m.start()].strip(" -_,")
                owner_addr = first[m.start():].strip(" -_,")
                return owner_name or None, owner_addr or None

            # If no digit, still might be just a name
            # e.g. "ADAMS, James"
            if re.search(r",", first):
                return first.strip() or None, None

    # 2) Fallback: old x-band split
    if not words:
        return None, None

    W = _page_width(words)
    if W <= 0:
        return None, None

    top_band = sorted(words, key=lambda w: w["bbox"][1])
    top_y = top_band[0]["bbox"][1]
    header_words = [w for w in words if w["bbox"][1] <= top_y + 40]
    header_words.sort(key=lambda w: w["bbox"][0])

    left = [w for w in header_words if w["bbox"][0] < W * 0.38]
    mid = [w for w in header_words if W * 0.38 <= w["bbox"][0] < W * 0.92]

    return _join(left) or None, _join(mid) or None


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
    # Fix common OCR: "6)" (where ')' looks like '1') => "61"
    norm = re.sub(r"\b(\d)\)", r"\11", norm)

    m = re.search(r"\bsex\s*([MF])\b", norm, flags=re.IGNORECASE)
    if m:
        sex = m.group(1).upper()

    # Age (handle OCR like "6)" meaning 61)
    m = re.search(r"\bage\s*([0-9\)\(]{1,3})\b", norm, flags=re.IGNORECASE)
    if m:
        a = m.group(1).replace(")", "1").replace("(", "1")
        a = re.sub(r"\D", "", a)
        age = a if a else None

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
        
        if type_of_grave:
            bad = _norm(type_of_grave)
            # If OCR basically returned label/fee fragments, treat as missing
            if "fee" in bad or "grave fee" in bad or bad in {"grave", "type", "type of", "type of grave"}:
                type_of_grave = None

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
def _parse_colon_bottom_row(line_texts: List[str]) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {"sex": None, "age": None, "type_of_grave": None, "grave_fee": None}

    row = None
    for ln in line_texts:
        if re.search(r"\bsex\s*:", ln, re.IGNORECASE) and re.search(r"\bage\s*:", ln, re.IGNORECASE):
            row = ln
            break
    if not row:
        return out

    # Normalize some OCR artifacts
    norm = row
    norm = norm.replace("_", " ")
    norm = re.sub(r"\s+", " ", norm).strip()

    m = re.search(r"\bSex\s*:\s*([MF])\b", norm, re.IGNORECASE)
    if m:
        out["sex"] = m.group(1).upper()

    m = re.search(r"\bAge\s*:\s*([0-9\)\(]{1,3})\b", norm, re.IGNORECASE)
    if m:
        a = m.group(1).replace(")", "1").replace("(", "1")
        a = re.sub(r"\D", "", a)
        out["age"] = a if a else None

    m = re.search(r"\bType\s+of\s+Grave\s*:\s*(.*?)(?=\bGrave\s*Fee\s*:|$)", norm, re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        # keep first 3 tokens to avoid spillover
        parts = val.split()
        out["type_of_grave"] = " ".join(parts[:3]) if parts else None

    m = re.search(r"\bGrave\s*Fee\s*:\s*([$0-9][0-9,.\- ]{0,15})", norm, re.IGNORECASE)
    if m:
        out["grave_fee"] = _extract_money(m.group(1)) or None

    return out

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
    owner_name, owner_address = _top_header_regions(words, line_texts=line_texts)

    header_ws = []
    if words:
        top_y = min(w["bbox"][1] for w in words)
        header_ws = [w for w in words if w["bbox"][1] <= top_y + 40]
        header_ws.sort(key=lambda w: w["bbox"][0])

    left_ws = [w for w in header_ws if w["bbox"][0] < W * 0.38]
    mid_ws = [w for w in header_ws if W * 0.38 <= w["bbox"][0] < W * 0.78]
    right_ws = [w for w in header_ws if w["bbox"][0] >= W * 0.78]

    # owner_address, owner_city2, owner_state2 = _cleanup_address_city(owner_address_raw, owner_city_state_raw)
    # if owner_city2:
    #     owner_city = owner_city2
    # if owner_state2:
    #     owner_state = owner_state2

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
    burial_anchor = _find_word(words, r"\b(burial|buriat|buriai|buria1)\b")
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

    # -------------------------
    # Step 1: PARKS fallback trigger
    # -------------------------
    missing_keys = {
        "phone": phone,
        "date_of_death": date_of_death,
        "date_of_burial": date_of_burial,
        "date_of_birth": date_of_birth,
        "grave_no": grave_no,
        "section_no": section_no,
        "block_side": block_side,
        "sex": sex,
        "age": age,
    }
    missing_count = sum(1 for v in missing_keys.values() if _is_missing(v))
    use_parks_fallback = _parks_like(all_text) and (missing_count >= 4)

        # -------------------------
    # Step 3: PARKS labelled-date fallback
    # -------------------------
    # -------------------------
    # PARKS labelled-date fallback (handles dual death/burial line)
    # -------------------------
    if use_parks_fallback:
        # first: try to handle the common combined line:
        # "Date of Death ... Date of Burial ... <date> ... <date>"
        for ln in line_texts:
            if re.search(r"\bdate\s+of\s+death\b", ln, re.IGNORECASE) and re.search(r"\bdate\s+of\s+bur(i|ia)l\b", ln, re.IGNORECASE):
                ds = _extract_two_dates_from_line(ln)
                # usually burial date appears first on this template line, then death appears below
                # but if we got two, assign in order: death then burial is ambiguous.
                # Better: if one is missing, fill both conservatively.
                if len(ds) >= 2:
                    if _is_missing(date_of_death):
                        date_of_death = ds[0]
                    if _is_missing(date_of_burial):
                        date_of_burial = ds[1]
                elif len(ds) == 1:
                    # if only one date present, let the labelled logic below decide
                    pass
                break

        # then: regular labelled extraction (same line + next lines)
        if _is_missing(date_of_death):
            date_of_death = _find_labelled_date(line_texts, r"\bdate\s+of\s+death\b")

        if _is_missing(date_of_burial):
            date_of_burial = _find_labelled_date(line_texts, r"\bdate\s+of\s+bur(i|ia)l\b")

        if _is_missing(date_of_birth):
            date_of_birth = _find_labelled_date(line_texts, r"\b(d(ate)?\s*of|dacof)\s+birth\b")

        # -------------------------
    # Step 4: PARKS description/section/block fallback
    # -------------------------
    if use_parks_fallback:
        d = _parse_description_and_section_block(line_texts)
        if _is_missing(lot_no) and d["lot_no"]:
            lot_no = d["lot_no"]
        if _is_missing(range_val) and d["range"]:
            range_val = d["range"]
        if _is_missing(grave_no) and d["grave_no"]:
            grave_no = d["grave_no"]
        if _is_missing(section_no) and d["section_no"]:
            section_no = d["section_no"]
        if _is_missing(block_side) and d["block_side"]:
            block_side = d["block_side"]

        # -------------------------
    # Step 5: PARKS colon-labelled Sex/Age/Type/Fee fallback
    # -------------------------
    if use_parks_fallback:
        b = _parse_colon_bottom_row(line_texts)
        if _is_missing(sex) and b["sex"]:
            sex = b["sex"]
        if _is_missing(age) and b["age"]:
            age = b["age"]
        if _is_missing(type_of_grave) and b["type_of_grave"]:
            type_of_grave = b["type_of_grave"]
        if _is_missing(grave_fee) and b["grave_fee"]:
            grave_fee = b["grave_fee"]

        # -------------------------
    # Step 6: PARKS header split fallback
    # -------------------------
    if use_parks_fallback:
        # If owner_name has digits or looks wrong, replace from header split.
        bad_name = (owner_name is None) or bool(re.search(r"\d", owner_name))
        bad_addr = _is_missing(owner_address)

        if bad_name or bad_addr:
            hn, ha = _split_header_name_address(line_texts)
            if bad_name and hn:
                owner_name = hn
            if bad_addr and ha:
                owner_address = ha

        # -------------------------
    # PARKS extra word-layout fallback for type + fee
    # -------------------------
    if use_parks_fallback:
        if _is_missing(type_of_grave) or _is_missing(grave_fee):
            t3, f3 = _parks_type_and_fee_from_words(words, W)
            if _is_missing(type_of_grave) and t3:
                type_of_grave = t3
            if _is_missing(grave_fee) and f3:
                grave_fee = f3

    return {
        "owner_name": _wrap(owner_name, left_ws),
        "owner_address": _wrap(owner_address, mid_ws),
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