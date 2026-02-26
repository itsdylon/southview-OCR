from __future__ import annotations
import sys, pprint
import cv2
from southview.ocr.preprocess import preprocess_array
from southview.ocr.tesseract_wrapper import run_tesseract
from southview.ocr.parser import parse_fields
from southview.ocr.confidence import add_confidence

def main(path: str) -> None:
    img = cv2.imread(path)
    pre = preprocess_array(img)
    ocr = run_tesseract(pre)
    print("=== RAW TEXT ===")
    print(ocr.get("raw_text", ""))

    parsed = parse_fields(ocr["words"])
    out = add_confidence(parsed, ocr["words"])

    print("\n=== FIELDS ===")
    pprint.pprint(out["fields"])
    print("\n=== FIELD CONFIDENCE (lowest first) ===")
    low = sorted(out["field_confidence"].items(), key=lambda kv: kv[1])
    pprint.pprint(low[:10])
    print("\ncard_confidence:", out["card_confidence"])

if __name__ == "__main__":
    main(sys.argv[1])