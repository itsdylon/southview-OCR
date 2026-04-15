"""Helpers for extraction manifest metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import southview.config as southview_config

EXTRACTION_METADATA_FIELDS = (
    "needs_review",
    "extraction_confidence",
    "stable_duration_frames",
    "selected_motion_score",
    "selected_sharpness",
    "duplicate_distance",
)


def frames_output_dir(video_id: str) -> Path:
    frames_root = Path(southview_config.get_config()["storage"]["frames_dir"])
    return frames_root / video_id


def extraction_manifest_path(video_id: str) -> Path:
    return frames_output_dir(video_id) / "extraction_manifest.json"


def normalize_image_path(image_path: str) -> str:
    return str(Path(image_path).expanduser().resolve(strict=False))


def load_extraction_manifest(video_id: str) -> dict[str, Any]:
    path = extraction_manifest_path(video_id)
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_capture_metadata_lookup(video_id: str) -> dict[str, dict[str, Any]]:
    manifest = load_extraction_manifest(video_id)
    accepted_frames = manifest.get("accepted_frames") or []
    lookup: dict[str, dict[str, Any]] = {}

    for item in accepted_frames:
        image_path = str(item.get("image_path") or "").strip()
        if not image_path:
            continue
        lookup[normalize_image_path(image_path)] = {
            field: item.get(field)
            for field in EXTRACTION_METADATA_FIELDS
        }

    return lookup
