import csv
from pathlib import Path
from southview.ocr.processor_min import process_card_min

def norm(s):
    return (s or "").strip()

def main():
    gt_path = Path("src\southview\ocr\ground_truth_min.csv")
    assert gt_path.exists(), f"Missing {gt_path}"

    rows = list(csv.DictReader(gt_path.open(newline="", encoding="utf-8")))
    total = len(rows)

    name_ok = 0
    dod_ok = 0
    dod_blank_ok = 0

    print("=== EVAL MIN ===")
    for r in rows:
        img_path = Path("example_cards") / r["filename"]
        out = process_card_min(str(img_path))
        pred = out["fields"]
        conf = out.get("field_confidence", {})

        gt_name = norm(r.get("owner_name"))
        gt_dod = norm(r.get("date_of_death"))

        pr_name = norm(pred.get("owner_name"))
        pr_dod = norm(pred.get("date_of_death"))

        ok_name = (pr_name == gt_name)
        ok_dod = (pr_dod == gt_dod)

        # if GT is blank, count as OK only if prediction is also blank
        ok_dod_blank = (gt_dod == "" and pr_dod == "")

        name_ok += 1 if ok_name else 0
        dod_ok += 1 if ok_dod else 0
        dod_blank_ok += 1 if ok_dod_blank else 0

        print(f"\n-- {r['filename']}")
        print("  NAME:", pr_name, "| gt:", gt_name, "| ok:", ok_name, "| conf:", conf.get("owner_name"))
        print("  DOD :", pr_dod,  "| gt:", gt_dod,  "| ok:", ok_dod,  "| conf:", conf.get("date_of_death"))
        print("  card_conf:", out.get("card_confidence"))

    print("\n=== SUMMARY ===")
    print("total:", total)
    print("name_accuracy:", name_ok / total if total else 0)
    print("dod_accuracy:", dod_ok / total if total else 0)
    print("dod_blank_ok_rate:", dod_blank_ok / total if total else 0)

if __name__ == "__main__":
    main()