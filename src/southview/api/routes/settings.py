from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from southview.config import get_config, _DEFAULT_CONFIG_PATH

router = APIRouter(tags=["settings"])


class ThresholdsPayload(BaseModel):
    auto_approve: float
    review_threshold: float


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

    # Persist to config.yaml with targeted replacements to preserve comments
    text = Path(_DEFAULT_CONFIG_PATH).read_text()
    text = re.sub(
        r"(auto_approve:\s*)[\d.]+",
        rf"\g<1>{payload.auto_approve}",
        text,
    )
    text = re.sub(
        r"(review_threshold:\s*)[\d.]+",
        rf"\g<1>{payload.review_threshold}",
        text,
    )
    Path(_DEFAULT_CONFIG_PATH).write_text(text)

    return {"status": "ok"}
