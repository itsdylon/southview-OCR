from __future__ import annotations

from typing import Any

import numpy as np

from southview.config import get_config
from southview.ocr.gemini_wrapper import gemini_engine_version, run_gemini
from southview.ocr.tesseract_wrapper import run_tesseract


def get_ocr_engine_name() -> str:
    return str(get_config().get("ocr", {}).get("engine", "tesseract")).strip().lower()


def uses_rotation_sweep() -> bool:
    cfg = get_config().get("ocr", {})
    engine = get_ocr_engine_name()
    if engine == "tesseract":
        return True
    if engine == "gemini":
        return bool(cfg.get("gemini", {}).get("try_rotations", False))
    return False


def get_ocr_engine_version() -> str:
    engine = get_ocr_engine_name()
    if engine == "gemini":
        return gemini_engine_version()
    return "tesseract"


def run_ocr(image: np.ndarray) -> dict[str, Any]:
    engine = get_ocr_engine_name()
    if engine == "tesseract":
        return run_tesseract(image)
    if engine == "gemini":
        return run_gemini(image)
    raise ValueError(f"Unsupported OCR engine: {engine}")
