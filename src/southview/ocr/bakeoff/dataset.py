from __future__ import annotations

import csv
import re
from pathlib import Path

from southview.ocr.bakeoff.normalize import normalize_date
from southview.ocr.bakeoff.types import ManifestRecord

REQUIRED_MANIFEST_COLUMNS = {
    "card_id",
    "image_path",
    "difficulty_bucket",
    "deceased_name",
    "date_of_death",
}


def _compact(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def load_manifest(manifest_path: str | Path) -> list[ManifestRecord]:
    path = Path(manifest_path)
    if not path.exists():
        raise ValueError(f"Manifest not found: {path}")

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        missing = REQUIRED_MANIFEST_COLUMNS - fieldnames
        if missing:
            cols = ", ".join(sorted(missing))
            raise ValueError(f"Manifest missing required columns: {cols}")

        records: list[ManifestRecord] = []
        for line_no, row in enumerate(reader, start=2):
            card_id = _compact(row.get("card_id"))
            if not card_id:
                raise ValueError(f"Manifest row {line_no}: card_id is required")

            image_raw = _compact(row.get("image_path"))
            if not image_raw:
                raise ValueError(f"Manifest row {line_no}: image_path is required")

            image_path = Path(image_raw)
            if not image_path.is_absolute():
                image_path = (path.parent / image_path).resolve()
            if not image_path.exists():
                raise ValueError(
                    f"Manifest row {line_no}: image_path does not exist: {image_path}"
                )

            difficulty_bucket = _compact(row.get("difficulty_bucket"))
            if not difficulty_bucket:
                raise ValueError(
                    f"Manifest row {line_no}: difficulty_bucket is required"
                )

            deceased_name = _compact(row.get("deceased_name"))

            dod_raw = _compact(row.get("date_of_death"))
            try:
                date_of_death = normalize_date(dod_raw, strict=True) if dod_raw else ""
            except ValueError as exc:
                raise ValueError(
                    f"Manifest row {line_no}: invalid date_of_death {dod_raw!r}"
                ) from exc

            records.append(
                ManifestRecord(
                    card_id=card_id,
                    image_path=str(image_path),
                    difficulty_bucket=difficulty_bucket,
                    deceased_name=deceased_name,
                    date_of_death=date_of_death,
                )
            )

    if not records:
        raise ValueError("Manifest is empty")

    return records
