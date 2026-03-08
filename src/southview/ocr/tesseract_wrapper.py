"""Tesseract OCR interface."""

import numpy as np
import pytesseract
from PIL import Image

from southview.config import get_config


def run_tesseract(image: np.ndarray) -> list[dict]:
    """
    Run Tesseract on a pre-processed image and return per-word data.

    Returns list of dicts with keys: text, conf, left, top, width, height,
    block_num, par_num, line_num, word_num.
    """
    config = get_config()
    tess_config = config["ocr"]["tesseract"]

    oem = tess_config.get("oem", 1)
    psm = tess_config.get("psm", )
    lang = tess_config.get("lang", "eng")

    custom_config = f"--oem {oem} --psm {psm}"

    pil_image = Image.fromarray(image)

    raw_text = pytesseract.image_to_string(pil_image, lang=lang, config=custom_config)

    data = pytesseract.image_to_data(
        pil_image, lang=lang, config=custom_config, output_type=pytesseract.Output.DICT
    )

    results = []
    n_boxes = len(data["text"])
    for i in range(n_boxes):
        text = data["text"][i].strip()
        conf_raw = data["conf"][i]
        try:
            conf = int(float(conf_raw))
        except Exception:
            conf = -1

        if conf == -1 or not text:
            continue

        left = int(data["left"][i])
        top = int(data["top"][i])
        width = int(data["width"][i])
        height = int(data["height"][i])
        conf = int(data["conf"][i])
        
        results.append({
            "text": text,
            "confidence": conf,   # <-- add this
            "conf": conf,         # <-- optional: keep for backward compatibility
            "left": data["left"][i],
            "top": data["top"][i],
            "width": data["width"][i],
            "height": data["height"][i],
            "bbox": [
                data["left"][i],
                data["top"][i],
                data["left"][i] + data["width"][i],
                data["top"][i] + data["height"][i],
            ],
            "block_num": data["block_num"][i],
            "par_num": data["par_num"][i],
            "line_num": data["line_num"][i],
            "word_num": data["word_num"][i],
        })

    return {"raw_text": raw_text or "", "words": results}
