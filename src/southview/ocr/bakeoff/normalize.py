from __future__ import annotations

import re
from datetime import datetime

from southview.ocr.parser_min import standardize_date_to_iso


def _collapse_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return _collapse_ws(value).casefold()


def normalize_date(value: str | None, *, strict: bool = False) -> str:
    if not value:
        return ""

    text = _collapse_ws(value)
    if not text:
        return ""

    # Allow already-normalized ISO dates in manifests and adjudication inputs.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            datetime.strptime(text, "%Y-%m-%d")
            return text
        except ValueError:
            if strict:
                raise ValueError(f"Invalid date format: {value!r}")
            return ""

    iso = standardize_date_to_iso(text)
    if iso:
        return iso

    if strict:
        raise ValueError(f"Invalid date format: {value!r}")
    return ""


def parse_optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None

    text = value.strip().lower()
    if not text:
        return None

    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False

    raise ValueError(
        f"Invalid boolean value {value!r}. Expected one of true/false/1/0/yes/no."
    )
