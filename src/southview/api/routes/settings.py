from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field, FiniteFloat
import yaml

from southview.config import get_config, _DEFAULT_CONFIG_PATH

router = APIRouter(tags=["settings"])


class ThresholdsPayload(BaseModel):
    auto_approve: FiniteFloat = Field(ge=0.0, le=1.0)
    review_threshold: FiniteFloat = Field(ge=0.0, le=1.0)


@router.get("/settings/thresholds")
def get_thresholds():
    cfg = get_config()
    conf = cfg.get("ocr", {}).get("confidence", {})
    return {
        "auto_approve": conf.get("auto_approve", 0.85),
        "review_threshold": conf.get("review_threshold", 0.70),
    }


@router.put("/settings/thresholds")
def update_thresholds(payload: ThresholdsPayload):
    # Update in-memory config
    cfg = get_config()
    cfg.setdefault("ocr", {}).setdefault("confidence", {})
    cfg["ocr"]["confidence"]["auto_approve"] = payload.auto_approve
    cfg["ocr"]["confidence"]["review_threshold"] = payload.review_threshold

    # Persist to config.yaml using structured YAML updates instead of regex replacements.
    config_path = Path(_DEFAULT_CONFIG_PATH)
    persisted = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    persisted.setdefault("ocr", {}).setdefault("confidence", {})
    persisted["ocr"]["confidence"]["auto_approve"] = payload.auto_approve
    persisted["ocr"]["confidence"]["review_threshold"] = payload.review_threshold
    config_path.write_text(
        yaml.safe_dump(persisted, sort_keys=False),
        encoding="utf-8",
    )

    return {"status": "ok"}
