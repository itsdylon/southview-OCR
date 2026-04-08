# src/southview/ocr/parser_min.py
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ----------------------------
# small geometry/text helpers
# ----------------------------
def _toknorm(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (t or "").lower())


def _group_words_into_lines(words: List[Dict[str, Any]], y_tol: int = 12) -> List[List[Dict[str, Any]]]:
    ws = [w for w in words if isinstance(w, dict) and w.get("text") and "bbox" in w]
    if not ws:
        return []
    ws.sort(key=lambda w: (w["bbox"][1], w["bbox"][0]))

    lines: List[List[Dict[str, Any]]] = []
    line_y: List[float] = []

    for w in ws:
        y1, y2 = w["bbox"][1], w["bbox"][3]
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

    lines.sort(key=lambda ln: sum((w["bbox"][1] + w["bbox"][3]) / 2.0 for w in ln) / len(ln))
    return lines


def _join(ws: List[Dict[str, Any]]) -> str:
    return " ".join(str(w.get("text", "")).strip() for w in ws if str(w.get("text", "")).strip()).strip()


def _words_in_y_band(words: List[Dict[str, Any]], y0: int, y1: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for w in words:
        if not isinstance(w, dict) or "bbox" not in w:
            continue
        _, wy0, _, wy1 = w["bbox"]
        if wy1 < y0 or wy0 > y1:
            continue
        if str(w.get("text", "")).strip():
            out.append(w)
    out.sort(key=lambda w: w["bbox"][0])
    return out


# ----------------------------
# date parsing + standardizing
# ----------------------------
_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_MONTH_RX = r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"


def _normalize_ocr_date_noise(s: str) -> str:
    if not s:
        return s
    s = s.replace("Qctober", "October").replace("0ctober", "October")
    s = s.replace("Qct.", "Oct").replace("0ct.", "Oct")
    s = s.replace("Buriat", "Burial").replace("Buria|", "Burial")
    s = s.replace("Dacof", "Date of")

    # 202] -> 2021 (SAFE backref)
    s = re.sub(r"(\d{3})\]", r"\g<1>1", s)
    # 20Z1 -> 2021 (only Z->2)
    s = re.sub(r"(\d{2})Z(\d)", r"\g<1>2\g<2>", s)

    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _extract_date_string(s: str) -> Optional[str]:
    if not s:
        return None
    t = _normalize_ocr_date_noise(s)

    m = re.search(rf"\b{_MONTH_RX}\.?\s+\d{{1,2}},\s*\d{{2,4}}\b", t, re.IGNORECASE)
    if m:
        return m.group(0)

    m = re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", t)
    if m:
        return m.group(0)

    return None


def _iso_to_dt(iso: str) -> Optional[datetime]:
    try:
        return datetime.strptime(iso, "%Y-%m-%d")
    except Exception:
        return None


def _normalize_two_digit_year(year: int) -> int:
    if year >= 100:
        return year
    # These burial cards are historical records, so 2-digit years should
    # default to the 1900s rather than rolling into the 2000s.
    return 1900 + year


def standardize_date_to_iso(s: str) -> Optional[str]:
    if not s:
        return None
    t = _normalize_ocr_date_noise(s)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s*,\s*", ", ", t)         # "30,2021" -> "30, 2021"
    t = re.sub(r"\.(?=\s)", "", t)          # "Oct." -> "Oct"
    t = re.sub(r"[^A-Za-z0-9,/ -]", "", t).strip()

    m = re.search(r"\b([A-Za-z]+)\s+(\d{1,2}),\s*(\d{2,4})\b", t)
    if m:
        mkey = m.group(1).lower()
        mon = _MONTHS.get(mkey) or _MONTHS.get(mkey[:4]) or _MONTHS.get(mkey[:3])
        if not mon:
            return None
        day = int(m.group(2))
        year = int(m.group(3))
        year = _normalize_two_digit_year(year)
        try:
            return datetime(year, mon, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", t)
    if m:
        mon, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        year = _normalize_two_digit_year(year)
        try:
            return datetime(year, mon, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    return None


# ----------------------------
# owner name standardization
# ----------------------------
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
_TITLES = {"mr", "mrs", "ms", "miss", "dr", "rev"}

def _remove_parenthetical_titles(s: str) -> str:
    """
    Remove (Mr.), (Ms,), (Mrs.), etc. but keep other content.
    """
    if not s:
        return s
    # remove parenthetical title variations
    s = re.sub(r"\(\s*(mr|mrs|ms|miss|dr)\.?,?\s*\)", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s)
    s = s.replace(" ,", ",")
    return s.strip().rstrip(",").strip()


def _name_token_clean(t: str) -> str:
    t = (t or "").strip()
    t = re.sub(r"^[^A-Za-z]+|[^A-Za-z.]+$", "", t)
    t = t.replace(".", "")
    return t


def standardize_owner_name_keep_suffix(s: str) -> Optional[str]:
    """
    Output format:
      LASTNAME (ALL CAPS), First Middle ...[, Suffix]
    Removes titles (including parenthetical titles), keeps suffix.
    """
    if not s:
        return None

    x = s.strip()
    x = re.sub(r"\([^)]*\)", "", x)  # remove parenthetical titles
    x = re.sub(r"\s+", " ", x)
    x = re.sub(r"\s*,\s*", ", ", x).strip().strip(" ,")

    if "," not in x:
        return x or None

    last, rest = x.split(",", 1)
    last = _name_token_clean(last).upper()
    rest = rest.strip()

    raw_tokens = re.split(r"[ \t]+", rest)
    tokens: List[str] = []
    suffix: Optional[str] = None

    for t in raw_tokens:
        t2 = _name_token_clean(t)
        if not t2:
            continue
        tl = t2.lower()
        if tl in _TITLES:
            continue
        if tl in _SUFFIXES:
            suffix = t2.title()
            continue
        tokens.append(t2)

    # catch suffix that appears after a comma in the rest
    rest_parts = [p.strip() for p in rest.split(",") if p.strip()]
    if rest_parts:
        tail = _name_token_clean(rest_parts[-1])
        if tail and tail.lower() in _SUFFIXES:
            suffix = tail.title()

    name_part = " ".join(tokens).strip()
    out = f"{last}, {name_part}".strip()
    if suffix:
        out = f"{out}, {suffix}"
    return out.strip().strip(",")


def _looks_like_label_line(s: str) -> bool:
    return bool(
        re.search(
            r"\b(date|death|burial|birth|owner|relation|contact|information|description|svc|sex|age|undertaker|grave\s*fee|type\s+of\s+grave|board\s+of\s+health)\b",
            s,
            re.I,
        )
    )


def _strip_address_tail(s: str) -> str:
    """
    If a line contains name + address jammed together, keep the name-like prefix.
    Heuristic: stop at first clear address signal (street number, common street tokens, zip).
    """
    if not s:
        return s

    # normalize spaces
    t = re.sub(r"\s+", " ", s).strip()

    # stop at a street number (e.g., "5566") if it appears after some letters
    m = re.match(r"^(.*?)(?=\s+\d{2,5}\b)", t)
    if m:
        return m.group(1).strip()

    # stop at obvious street words (very light list; expand if needed)
    m = re.match(r"^(.*?)(?=\s+\b(road|rd|street|st|ave|avenue|blvd|drive|dr|lane|ln|way|hwy)\b)", t, re.I)
    if m:
        return m.group(1).strip()

    # stop at ZIP-like
    m = re.match(r"^(.*?)(?=\s+\d{5}(?:-\d{4})?\b)", t)
    if m:
        return m.group(1).strip()

    return t


def parse_owner_name_from_words(words: List[Dict[str, Any]]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    lines = _group_words_into_lines(words, y_tol=12)
    if not lines:
        return None, []

    texts = [_join(ln) for ln in lines]

    def _is_bad_name_line(t: str) -> bool:
        tt = t.lower()
        return (
            "c/o" in tt
            or "estate" in tt
            or "owner" in tt
            or "relation" in tt
            or "contact" in tt
            or "information" in tt
            or "date" in tt
            or "death" in tt
            or "burial" in tt
            or "birth" in tt
            or "description" in tt
            or "undertaker" in tt
            or "svc" in tt
        )

    def _strip_titles_parentheses(s: str) -> str:
        # Remove (Mr.), (Ms,), (Mrs.), etc.
        s = re.sub(r"\(\s*(mr|mrs|ms|miss|dr)\.?,?\s*\)", "", s, flags=re.I)
        s = re.sub(r"\s+", " ", s)
        s = s.replace(" ,", ",")
        return s.strip().rstrip(",").strip()

    def _strip_after_first_number(s: str) -> str:
        # "Benjamin L. 5566 Marbut Road" -> "Benjamin L."
        m = re.match(r"^(.*?)(?=\s+\d{2,5}\b|$)", s.strip())
        return (m.group(1) if m else s).strip()

    # ---------------------------------------------------
    # 1) Prefer real "LAST, First..." line
    # ---------------------------------------------------
    best_full_i = None
    best_full_score = -10**9

    for i, t in enumerate(texts[:6]):
        if not t or _is_bad_name_line(t):
            continue
        if re.search(r"\b\d{2,5}\b", t):  # address line
            continue

        m = re.match(r"^\s*([A-Z][A-Z'\-]{2,}),\s*([A-Za-z].+)$", t)
        if not m:
            continue

        comma_pos = t.find(",")
        score = 100 - comma_pos
        if score > best_full_score:
            best_full_score = score
            best_full_i = i

    if best_full_i is not None:
        name = _strip_titles_parentheses(texts[best_full_i])
        return (name or None), lines[best_full_i]

    # ---------------------------------------------------
    # 2) Handle split case: "LAST," on one line
    # ---------------------------------------------------
    best_last_i = None
    best_last_score = -10**9

    for i, t in enumerate(texts[:8]):
        if not t or _is_bad_name_line(t):
            continue
        if re.search(r"\b\d{2,5}\b", t):
            continue

        m = re.match(r"^\s*([A-Z][A-Z'\-]{2,})\s*,?\s*$", t)
        if not m:
            continue

        score = 1000 - i
        if score > best_last_score:
            best_last_score = score
            best_last_i = i

    if best_last_i is not None:
        last = re.match(r"^\s*([A-Z][A-Z'\-]{2,})", texts[best_last_i]).group(1)

        first_mid = None
        support_lines = [lines[best_last_i]]

        # Pull FIRST/MIDDLE from line ABOVE
        if best_last_i - 1 >= 0:
            up = texts[best_last_i - 1]
            if up and not _is_bad_name_line(up):
                up = _strip_after_first_number(up)
                up = _strip_titles_parentheses(up)

                toks = up.split()
                if toks:
                    first_mid = " ".join(toks[:3])
                    support_lines.insert(0, lines[best_last_i - 1])

        if first_mid:
            name = f"{last}, {first_mid}".strip()
            name = _strip_titles_parentheses(name)
            return name, [w for ln in support_lines for w in ln]

        return f"{last},".strip(), lines[best_last_i]

    # ---------------------------------------------------
    # 3) Fallback: top line
    # ---------------------------------------------------
    top_text = texts[0]
    top_text = _strip_titles_parentheses(_strip_after_first_number(top_text))
    return (top_text or None), lines[0]


def parse_owner_name_from_text(raw_text: str) -> Optional[str]:
    if not raw_text:
        return None

    lines = [re.sub(r"\s+", " ", ln).strip() for ln in raw_text.splitlines() if ln.strip()]
    if not lines:
        return None

    for line in lines[:5]:
        candidate = _remove_parenthetical_titles(_strip_address_tail(line))
        if not candidate or _looks_like_label_line(candidate):
            continue

        lower = candidate.lower()
        if "c/o" in lower or "estate" in lower:
            continue

        if "," in candidate:
            return candidate.strip().rstrip(",")

    first = _remove_parenthetical_titles(_strip_address_tail(lines[0]))
    return first.strip().rstrip(",") or None


def _lines(raw_text: str) -> List[str]:
    return [re.sub(r"\s+", " ", ln).strip() for ln in raw_text.splitlines() if ln.strip()]


def _find_line_after_label(
    lines: List[str],
    label_pattern: str,
    max_lookahead: int = 3,
    skip_patterns: List[str] | None = None,
    stop_on_label: bool = False,
) -> Optional[str]:
    rx = re.compile(label_pattern, re.IGNORECASE)
    skip_res = [re.compile(p, re.IGNORECASE) for p in (skip_patterns or [])]
    for i, line in enumerate(lines):
        m = rx.search(line)
        if not m:
            continue

        tail = line[m.end():].strip(" :-")
        if tail and not any(sr.search(tail) for sr in skip_res):
            return tail

        for j in range(i + 1, min(len(lines), i + 1 + max_lookahead)):
            candidate = lines[j].strip()
            if not candidate:
                continue
            if stop_on_label and _looks_like_label_line(candidate):
                break
            if any(sr.search(candidate) for sr in skip_res):
                continue
            if not _looks_like_label_line(candidate):
                return candidate
    return None


def _find_line_before_label(
    lines: List[str],
    label_pattern: str,
    max_lookbehind: int = 2,
    skip_patterns: List[str] | None = None,
) -> Optional[str]:
    rx = re.compile(label_pattern, re.IGNORECASE)
    skip_res = [re.compile(p, re.IGNORECASE) for p in (skip_patterns or [])]
    for i, line in enumerate(lines):
        if not rx.search(line):
            continue

        for j in range(i - 1, max(-1, i - 1 - max_lookbehind), -1):
            candidate = lines[j].strip()
            if not candidate:
                continue
            if any(sr.search(candidate) for sr in skip_res):
                continue
            if _looks_like_label_line(candidate):
                break
            return candidate
    return None


def _collect_lines_after_label(
    lines: List[str],
    label_pattern: str,
    max_lookahead: int = 4,
    skip_patterns: List[str] | None = None,
) -> List[str]:
    rx = re.compile(label_pattern, re.IGNORECASE)
    skip_res = [re.compile(p, re.IGNORECASE) for p in (skip_patterns or [])]
    for i, line in enumerate(lines):
        m = rx.search(line)
        if not m:
            continue

        out: List[str] = []
        tail = line[m.end():].strip(" :-")
        if tail and not any(sr.search(tail) for sr in skip_res):
            out.append(tail)

        for j in range(i + 1, min(len(lines), i + 1 + max_lookahead)):
            candidate = lines[j].strip()
            if not candidate:
                continue
            if any(sr.search(candidate) for sr in skip_res):
                continue
            if _looks_like_label_line(candidate):
                break
            out.append(candidate)

        return out
    return []


def _find_address_from_text(lines: List[str]) -> Optional[str]:
    for line in lines[:8]:
        lower = line.lower()
        if "date of" in lower or "relation" in lower or "description" in lower or "ph#" in lower:
            continue
        if _extract_date_string(line):
            continue
        if re.search(r"\b\d{2,6}\b", line):
            cleaned = re.sub(r"^\s*ph#?.*$", "", line, flags=re.IGNORECASE).strip()
            if cleaned:
                return cleaned
    return None


def _extract_phone_from_text(raw_text: str) -> Optional[str]:
    m = re.search(r"(\(?\d{3}\)?\s*[-./]?\s*\d{3}\s*[-./]?\s*\d{4})", raw_text)
    return m.group(1) if m else None


def _extract_date_from_label(lines: List[str], label_pattern: str) -> Optional[str]:
    candidates = _collect_lines_after_label(
        lines,
        label_pattern,
        skip_patterns=[r"\bdob\b", r"\bdate\s+of\s+birth\b"],
    )
    for text in candidates:
        trimmed = re.split(
            r"\b(date\s+of\s+death|date\s+of\s+burial|burial|date\s+of\s+birth|dob)\b",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()
        if not trimmed:
            continue
        d = _extract_date_string(trimmed)
        if d:
            iso = standardize_date_to_iso(d)
            if iso:
                return iso
    return None


def _extract_unlabeled_dates_before_dob(lines: List[str]) -> tuple[Optional[str], Optional[str]]:
    dob_index = None
    for i, line in enumerate(lines):
        if re.search(r"\bdob\b|\bdate\s+of\s+birth\b", line, re.IGNORECASE):
            dob_index = i
            break

    if dob_index is None:
        return None, None

    candidates: list[str] = []
    for line in lines[:dob_index]:
        text = line.strip()
        if not text or _looks_like_label_line(text):
            continue
        if _extract_phone_from_text(text):
            continue
        d = _extract_date_string(text)
        if not d:
            continue
        iso = standardize_date_to_iso(d)
        if iso:
            candidates.append(iso)

    if len(candidates) >= 2:
        first = candidates[-2]
        second = candidates[-1]
        if first == second:
            # If OCR duplicated the same unlabeled date twice, treat it as a
            # likely burial-only signal rather than populating both fields
            # with the same wrong value.
            return None, second
        return first, second
    if len(candidates) == 1:
        return candidates[0], None
    return None, None


def _extract_inline_date_after_label(line: str, label_pattern: str, stop_pattern: str | None = None) -> Optional[str]:
    rx = re.compile(label_pattern, re.IGNORECASE)
    m = rx.search(line)
    if not m:
        return None

    tail = line[m.end():].strip()
    if stop_pattern:
        tail = re.split(stop_pattern, tail, maxsplit=1, flags=re.IGNORECASE)[0].strip()

    d = _extract_date_string(tail)
    if not d:
        return None
    return standardize_date_to_iso(d)


def _extract_description(lines: List[str]) -> Optional[str]:
    parts = _collect_lines_after_label(lines, r"\bdescription\b", max_lookahead=5)
    if not parts:
        location_lines: List[str] = []
        for line in lines:
            lower = line.lower()
            if _looks_like_label_line(line) and not re.search(r"\b(direction|section|lot|range|grave|block)\b", lower):
                continue
            if re.fullmatch(r"direction\s*:?", lower):
                continue
            if re.search(r"\b(lot|range|grave|section|block|direction|northside|southside|eastside|westside)\b", lower):
                if line not in location_lines:
                    location_lines.append(line)
        if location_lines:
            return " ".join(location_lines).strip() or None
        return None
    return " ".join(parts).strip() or None


def _extract_simple_field(raw_text: str, pattern: str, group: int = 1) -> Optional[str]:
    m = re.search(pattern, raw_text, re.IGNORECASE)
    if not m:
        return None
    value = m.group(group).strip()
    return value or None


def _extract_unlabeled_svc_no(lines: List[str]) -> Optional[str]:
    for i, line in enumerate(lines):
        if not re.search(r"\bgrave\s*fee\b", line, re.IGNORECASE):
            continue
        for j in range(i + 1, min(len(lines), i + 4)):
            candidate = lines[j].strip()
            if not candidate:
                continue
            if _looks_like_label_line(candidate):
                continue
            if re.fullmatch(r"[0-9]{1,3}(?:,[0-9]{3})+", candidate) or re.fullmatch(r"[0-9]{3,}", candidate):
                return candidate
    return None


def _clean_undertaker(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = re.sub(r"\s+", " ", value).strip(" :-")
    if not value:
        return None
    if value.lower() in {"grave", "fee", "sex", "age", "type", "description", "owner", "relation"}:
        return None
    if _looks_like_label_line(value):
        return None
    if _extract_date_string(value):
        return None
    return value


def parse_fields_from_text(raw_text: str) -> Dict[str, Dict[str, Any]]:
    lines = _lines(raw_text)
    owner_name = parse_owner_name_from_text(raw_text)
    address = _find_address_from_text(lines)
    owner = _find_line_after_label(
        lines,
        r"\bc\/o\b",
        skip_patterns=[r"^\s*owner\s*$"],
        stop_on_label=True,
    ) or _find_line_after_label(lines, r"\bowner\b", stop_on_label=True)
    relation = _find_line_after_label(lines, r"\brelation\b", stop_on_label=True)
    phone = _extract_phone_from_text(raw_text)
    date_of_death = parse_date_of_death_from_text(raw_text)
    if not date_of_death:
        date_of_death = _extract_date_from_label(lines, r"\bdate\s+of\s+death\b")
    date_of_burial = _extract_date_from_label(lines, r"\bdate\s+of\s+burial\b|\bburial\b")
    if not date_of_death and not date_of_burial:
        unlabeled_dod, unlabeled_doburial = _extract_unlabeled_dates_before_dob(lines)
        date_of_death = unlabeled_dod
        date_of_burial = unlabeled_doburial
    description = _extract_description(lines)
    sex = _extract_simple_field(raw_text, r"\bsex\b\s*:?\s*([MF])\b")
    age = _extract_simple_field(raw_text, r"\bage\b\s*:?\s*([0-9]{1,3})\b")
    grave_type = _find_line_after_label(lines, r"\btype\s+of\s+grave\b", stop_on_label=True)
    if not grave_type:
        grave_type = _extract_simple_field(
            raw_text,
            r"\btype\s+of\s+grave\b\s*:?\s*(.*?)(?=\bgrave\s*fee\b|\bundertaker\b|\bsvc\b|$)",
        )
    grave_fee = _extract_simple_field(raw_text, r"\bgrave\s*fee\b\s*:?\s*\$?\s*([0-9]{2,4}(?:\.[0-9]{2})?)")
    undertaker = _find_line_after_label(lines, r"\bundertaker\b", stop_on_label=True)
    if not undertaker:
        undertaker = _find_line_before_label(
            lines,
            r"\bundertaker\b",
            skip_patterns=[r"\bboard\s+of\s+health\b", r"\bdate\s+of\b"],
        )
    board_of_health_no = _find_line_after_label(lines, r"\bboard\s+of\s+health\s+no\.?\b")
    svc_no = _find_line_after_label(lines, r"\bsvc\s+no\.?\b") or _extract_simple_field(raw_text, r"\bsvc\s+no\.?\b\s*:?\s*([A-Za-z0-9,-]+)")
    if not svc_no:
        svc_no = _extract_unlabeled_svc_no(lines)

    if grave_type:
        grave_type = re.sub(r"\s+", " ", grave_type).strip(" :-")
        if _looks_like_label_line(grave_type):
            grave_type = None
    if description:
        description = re.sub(r"\s+", " ", description).strip(" :-")
    undertaker = _clean_undertaker(undertaker)
    if svc_no and board_of_health_no == svc_no:
        board_of_health_no = None
    if svc_no:
        svc_no = re.sub(r"[^0-9A-Za-z,-]", "", svc_no)

    return {
        "owner_name": {"value": owner_name, "support": []},
        "owner_address": {"value": address, "support": []},
        "care_of": {"value": owner, "support": []},
        "relation": {"value": relation, "support": []},
        "phone": {"value": phone, "support": []},
        "date_of_death": {"value": date_of_death, "support": []},
        "date_of_burial": {"value": date_of_burial, "support": []},
        "description": {"value": description, "support": []},
        "sex": {"value": sex, "support": []},
        "age": {"value": age, "support": []},
        "type_of_grave": {"value": grave_type, "support": []},
        "grave_fee": {"value": grave_fee, "support": []},
        "undertaker": {"value": undertaker, "support": []},
        "board_of_health_no": {"value": board_of_health_no, "support": []},
        "svc_no": {"value": svc_no, "support": []},
    }


# ----------------------------
# Date of death extraction
# ----------------------------
def extract_date_after_label(raw_text: str, *, label: str) -> Optional[str]:
    """
    Extract a raw date substring from the SAME LINE as the label.
    Important: if the line contains multiple dates, returns the FIRST date found after cutting at next labels.
    """
    if not raw_text:
        return None

    lines = [_normalize_ocr_date_noise(x) for x in raw_text.splitlines() if x.strip()]
    label_rx = re.compile(label, re.IGNORECASE)

    for ln in lines:
        m = label_rx.search(ln)
        if not m:
            continue
        tail = ln[m.end():].strip()

        # cut off at next label if OCR jammed them together
        tail_cut = re.split(
            r"\bDate of Birth\b|\bDOB\b|\bDate of Burial\b|\bBurial\b",
            tail,
            flags=re.IGNORECASE,
        )[0].strip()

        d = _extract_date_string(tail_cut)
        if d:
            return d

    return None


def parse_date_of_death_from_text(raw_text: str) -> Optional[str]:
    if not raw_text:
        return None

    lines = [_normalize_ocr_date_noise(x) for x in raw_text.splitlines() if x.strip()]
    death_rx = re.compile(r"\bdate\s+of\s+death\b", re.IGNORECASE)
    hard_stop_rx = re.compile(
        r"\b(date\s+of\s+burial|burial|date\s+of\s+birth|dob|undertaker|svc|description|sex|age)\b",
        re.IGNORECASE,
    )

    for i, ln in enumerate(lines):
        m = death_rx.search(ln)
        if not m:
            continue

        same_line_iso = _extract_inline_date_after_label(
            ln,
            r"\bdate\s+of\s+death\b",
            stop_pattern=r"\b(date\s+of\s+burial|burial|date\s+of\s+birth|dob)\b",
        )
        if same_line_iso:
            return same_line_iso

        tail = ln[m.end():].strip()
        if re.search(r"\b(date\s+of\s+burial|burial)\b", tail, re.IGNORECASE):
            return None

        for j in range(i + 1, min(i + 4, len(lines))):
            candidate = lines[j].strip()
            if not candidate:
                continue
            if hard_stop_rx.search(candidate):
                break
            d = _extract_date_string(candidate)
            iso = standardize_date_to_iso(d) if d else None
            if iso:
                return iso

        return None

    return None


def parse_date_of_death_from_words(words: List[Dict[str, Any]]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    death_tokens = [
        w for w in words
        if isinstance(w, dict) and w.get("text") and "bbox" in w and "death" in _toknorm(str(w["text"]))
    ]
    if not death_tokens:
        return None, []

    death_tokens.sort(key=lambda w: (w.get("conf", w.get("confidence", 0))), reverse=True)
    anchor = death_tokens[0]
    ax2, ay1, ay2 = anchor["bbox"][2], anchor["bbox"][1], anchor["bbox"][3]

    band = _words_in_y_band(words, ay1 - 18, ay2 + 18)
    right = [w for w in band if w["bbox"][0] >= ax2 + 4]

    cut = len(right)
    for i, w in enumerate(right):
        tt = _toknorm(str(w.get("text", "")))
        if "burial" in tt or "birth" in tt or tt == "dob":
            cut = i
            break
    right = right[:cut]

    snippet = _normalize_ocr_date_noise(_join(right))
    iso = standardize_date_to_iso(snippet)
    if iso:
        return iso, right

    return None, []


# ----------------------------
# main minimal parser
# ----------------------------
def parse_fields_min(words: List[Dict[str, Any]], raw_text: str = "") -> Dict[str, Any]:
    if not words and raw_text:
        return parse_fields_from_text(raw_text)

    owner_name, owner_ws = parse_owner_name_from_words(words)
    if owner_name is None:
        owner_name = parse_owner_name_from_text(raw_text)

    # 1) same-line death label
    dod_raw = extract_date_after_label(raw_text, label=r"\bDate\s+of\s+Death\b")
    dod_iso = standardize_date_to_iso(dod_raw) if dod_raw else None

    # 2) multi-line / multi-candidate heuristic (fixes Barbara case)
    if dod_iso is None:
        dod_iso = parse_date_of_death_from_text(raw_text)

    # 3) bbox-based fallback
    dod_ws: List[Dict[str, Any]] = []
    if dod_iso is None:
        dod_iso, dod_ws = parse_date_of_death_from_words(words)

    return {
        "owner_name": {"value": owner_name, "support": [w["bbox"] for w in owner_ws]},
        "date_of_death": {"value": dod_iso, "support": [w["bbox"] for w in dod_ws]},
    }
