from __future__ import annotations
import pprint
from southview.ocr.processor import process_card

CASES = [
    {
        "name": "AARON",
        "path": r"C:\Users\level\Desktop\South_View_OCR\southview-OCR\example_cards\AARON_BENJAMIN(NEW).png",
        "expected": {
            "owner_name": "AARON, Benjamin L.",
            "lot_no": "316",
            "range": "B",
            "grave_no": "2",
            "section_no": "4",
            "block_side": "Block 5 Northside",
            "sex": "M",
            "age": "38",
        },
        "must_not_be_none": ["date_of_death", "date_of_burial", "date_of_birth"],
    },
    {
        "name": "ADAMS",
        "path": r"C:\Users\level\Desktop\South_View_OCR\southview-OCR\example_cards\ADAMS_JAMES(NEW).png",
        "expected": {
            "owner_name": "ADAMS, James",
            "lot_no": "64",
            "range": "G",
            "grave_no": "9",
            "section_no": "2",
            "sex": "M",
            "age": "54",
            "undertaker": "Cox",
        },
        "must_not_be_none": [],
    },
]

def _fail(msg: str) -> None:
    raise SystemExit(msg)

def main() -> None:
    for c in CASES:
        out = process_card(c["path"])
        fields = out["fields"]

        # exact matches
        for k, v in c["expected"].items():
            if fields.get(k) != v:
                print("\nFAILED:", c["name"])
                print("Field:", k, "Expected:", v, "Got:", fields.get(k))
                print("All fields:")
                pprint.pprint(fields)
                _fail("regression failed")

        # not-none checks
        for k in c["must_not_be_none"]:
            if fields.get(k) is None:
                print("\nFAILED:", c["name"])
                print("Field:", k, "Expected: not None, Got: None")
                pprint.pprint(fields)
                _fail("regression failed")

        print("PASS:", c["name"], "card_conf:", out.get("card_confidence"))

    print("\nALL REGRESSIONS PASS")

if __name__ == "__main__":
    main()