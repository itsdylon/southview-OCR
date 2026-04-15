from __future__ import annotations

import fcntl
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

    # Persist to config.yaml under an exclusive file lock to avoid concurrent overwrites.
    config_path = Path(_DEFAULT_CONFIG_PATH)
    with config_path.open("r+", encoding="utf-8") as config_file:
        fcntl.flock(config_file.fileno(), fcntl.LOCK_EX)
        persisted = yaml.safe_load(config_file.read()) or {}
        persisted.setdefault("ocr", {}).setdefault("confidence", {})
        persisted["ocr"]["confidence"]["auto_approve"] = payload.auto_approve
        persisted["ocr"]["confidence"]["review_threshold"] = payload.review_threshold
        config_file.seek(0)
        config_file.write(yaml.safe_dump(persisted, sort_keys=False))
        config_file.truncate()
        config_file.flush()
        fcntl.flock(config_file.fileno(), fcntl.LOCK_UN)

    return {"status": "ok"}
