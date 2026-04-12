from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

from sqlalchemy import select

from southview.config import get_config
from southview.db.engine import get_session
from southview.db.models import Card, OCRResult


class ExportIncompleteError(ValueError):
    """Raised when an export cannot be completed with all referenced files."""


def _slug(s: str | None, max_len: int = 80) -> str:
    s = (s or "").strip().upper()
    s = re.sub(r"[^A-Z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "UNKNOWN"
    return s[:max_len]


def export_approved_cards_zip(
    video_id: str,
    include_corrected: bool = True,
) -> Path:
    """
    Copy approved/corrected card images for a video into exports_dir, name them, and return a ZIP path.
    """
    cfg = get_config()
    exports_root = Path(cfg["storage"]["exports_dir"]).resolve()
    out_dir = exports_root / "videos" / video_id

    statuses = {"approved"}
    if include_corrected:
        statuses.add("corrected")

    session = get_session()
    try:
        # join cards -> ocr_results to filter by review_status
        stmt = (
            select(Card, OCRResult)
            .join(OCRResult, OCRResult.card_id == Card.id)
            .where(Card.video_id == video_id)
            .where(OCRResult.review_status.in_(sorted(statuses)))
            .order_by(Card.sequence_index.asc())
        )
        rows = session.execute(stmt).all()

        if not rows:
            raise ValueError("No approved/corrected cards found for this video_id")

        copy_plan: list[tuple[Path, Path]] = []
        missing_sources: list[Path] = []
        for card, ocr in rows:
            src = Path(card.image_path).resolve()
            if not src.exists():
                missing_sources.append(src)
                continue

            name = _slug(ocr.deceased_name, 80)
            dod = _slug(ocr.date_of_death, 20)
            seq = f"{card.sequence_index:03d}"

            dst = out_dir / f"{name}_{dod}__card_{seq}{src.suffix}"
            copy_plan.append((src, dst))

        if missing_sources:
            preview = ", ".join(path.name for path in missing_sources[:3])
            if len(missing_sources) > 3:
                preview = f"{preview}, ..."
            raise ExportIncompleteError(
                f"Cannot export video {video_id}: {len(missing_sources)} source image(s) are missing ({preview})."
            )

        out_dir.mkdir(parents=True, exist_ok=True)
        exported_files: list[Path] = []
        for src, dst in copy_plan:
            shutil.copy2(src, dst)
            exported_files.append(dst)

        zip_path = out_dir / f"{video_id}_export.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for f in exported_files:
                z.write(f, arcname=f.name)

        return zip_path
    finally:
        session.close()
