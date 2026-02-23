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
    psm = tess_config.get("psm", 6)
    lang = tess_config.get("lang", "eng")

    custom_config = f"--oem {oem} --psm {psm}"

    pil_image = Image.fromarray(image)

    data = pytesseract.image_to_data(
        pil_image, lang=lang, config=custom_config, output_type=pytesseract.Output.DICT
    )

    results = []
    n_boxes = len(data["text"])
    for i in range(n_boxes):
        text = data["text"][i].strip()
        conf = int(data["conf"][i])

        if conf == -1 or not text:
            continue

        results.append({
            "text": text,
            "conf": conf,
            "left": data["left"][i],
            "top": data["top"][i],
            "width": data["width"][i],
            "height": data["height"][i],
            "block_num": data["block_num"][i],
            "par_num": data["par_num"][i],
            "line_num": data["line_num"][i],
            "word_num": data["word_num"][i],
        })

    return results
