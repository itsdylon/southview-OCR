from __future__ import annotations

import csv
import json
from pathlib import Path

from southview.ocr.bakeoff.normalize import parse_optional_bool
from southview.ocr.bakeoff.types import AdjudicationRecord, PredictionRecord

PREDICTIONS_FILENAME = "predictions.csv"
ADJUDICATION_FILENAME = "adjudication.csv"
SUMMARY_JSON_FILENAME = "summary.json"
SUMMARY_MD_FILENAME = "summary.md"

PREDICTION_COLUMNS = [
    "card_id",
    "image_path",
    "difficulty_bucket",
    "model_id",
    "gt_deceased_name",
    "gt_date_of_death",
    "pred_deceased_name",
    "pred_date_of_death",
    "normalized_gt_name",
    "normalized_gt_dod",
    "normalized_pred_name",
    "normalized_pred_dod",
    "name_match",
    "dod_match",
    "exact_match",
    "latency_ms",
    "error",
    "usage_json",
    "raw_text",
]

ADJUDICATION_COLUMNS = [
    "card_id",
    "image_path",
    "difficulty_bucket",
    "model_id",
    "gt_deceased_name",
    "gt_date_of_death",
    "pred_deceased_name",
    "pred_date_of_death",
    "name_match",
    "dod_match",
    "exact_match",
    "human_name_correct",
    "human_dod_correct",
    "adjudication_notes",
]


def _bool_to_str(value: bool) -> str:
    return "true" if value else "false"


def _str_to_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def write_predictions_csv(path: str | Path, predictions: list[PredictionRecord]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PREDICTION_COLUMNS)
        writer.writeheader()
        for p in predictions:
            writer.writerow(
                {
                    "card_id": p.card_id,
                    "image_path": p.image_path,
                    "difficulty_bucket": p.difficulty_bucket,
                    "model_id": p.model_id,
                    "gt_deceased_name": p.gt_deceased_name,
                    "gt_date_of_death": p.gt_date_of_death,
                    "pred_deceased_name": p.pred_deceased_name,
                    "pred_date_of_death": p.pred_date_of_death,
                    "normalized_gt_name": p.normalized_gt_name,
                    "normalized_gt_dod": p.normalized_gt_dod,
                    "normalized_pred_name": p.normalized_pred_name,
                    "normalized_pred_dod": p.normalized_pred_dod,
                    "name_match": _bool_to_str(p.name_match),
                    "dod_match": _bool_to_str(p.dod_match),
                    "exact_match": _bool_to_str(p.exact_match),
                    "latency_ms": f"{p.latency_ms:.3f}",
                    "error": p.error,
                    "usage_json": p.usage_json,
                    "raw_text": p.raw_text,
                }
            )

    return out


def read_predictions_csv(path: str | Path) -> list[PredictionRecord]:
    src = Path(path)
    if not src.exists():
        raise ValueError(f"Missing predictions.csv: {src}")

    with src.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        records: list[PredictionRecord] = []
        for row in reader:
            records.append(
                PredictionRecord(
                    card_id=row.get("card_id", ""),
                    image_path=row.get("image_path", ""),
                    difficulty_bucket=row.get("difficulty_bucket", ""),
                    model_id=row.get("model_id", ""),
                    gt_deceased_name=row.get("gt_deceased_name", ""),
                    gt_date_of_death=row.get("gt_date_of_death", ""),
                    pred_deceased_name=row.get("pred_deceased_name", ""),
                    pred_date_of_death=row.get("pred_date_of_death", ""),
                    normalized_gt_name=row.get("normalized_gt_name", ""),
                    normalized_gt_dod=row.get("normalized_gt_dod", ""),
                    normalized_pred_name=row.get("normalized_pred_name", ""),
                    normalized_pred_dod=row.get("normalized_pred_dod", ""),
                    name_match=_str_to_bool(row.get("name_match", "false")),
                    dod_match=_str_to_bool(row.get("dod_match", "false")),
                    exact_match=_str_to_bool(row.get("exact_match", "false")),
                    latency_ms=float(row.get("latency_ms") or 0.0),
                    error=row.get("error", ""),
                    usage_json=row.get("usage_json", "{}"),
                    raw_text=row.get("raw_text", ""),
                )
            )
    return records


def write_adjudication_csv(path: str | Path, predictions: list[PredictionRecord]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    mismatches = [p for p in predictions if not p.exact_match]

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ADJUDICATION_COLUMNS)
        writer.writeheader()
        for p in mismatches:
            writer.writerow(
                {
                    "card_id": p.card_id,
                    "image_path": p.image_path,
                    "difficulty_bucket": p.difficulty_bucket,
                    "model_id": p.model_id,
                    "gt_deceased_name": p.gt_deceased_name,
                    "gt_date_of_death": p.gt_date_of_death,
                    "pred_deceased_name": p.pred_deceased_name,
                    "pred_date_of_death": p.pred_date_of_death,
                    "name_match": _bool_to_str(p.name_match),
                    "dod_match": _bool_to_str(p.dod_match),
                    "exact_match": _bool_to_str(p.exact_match),
                    "human_name_correct": "",
                    "human_dod_correct": "",
                    "adjudication_notes": "",
                }
            )

    return out


def read_adjudication_csv(path: str | Path) -> list[AdjudicationRecord]:
    src = Path(path)
    if not src.exists():
        raise ValueError(f"Adjudication file not found: {src}")

    with src.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        records: list[AdjudicationRecord] = []
        for line_no, row in enumerate(reader, start=2):
            try:
                records.append(
                    AdjudicationRecord(
                        card_id=(row.get("card_id") or "").strip(),
                        model_id=(row.get("model_id") or "").strip(),
                        human_name_correct=parse_optional_bool(row.get("human_name_correct")),
                        human_dod_correct=parse_optional_bool(row.get("human_dod_correct")),
                        adjudication_notes=(row.get("adjudication_notes") or "").strip(),
                    )
                )
            except ValueError as exc:
                raise ValueError(f"Invalid adjudication row {line_no}: {exc}") from exc

    return records


def write_summary_json(path: str | Path, summary: dict) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def default_run_paths(run_dir: str | Path) -> dict[str, Path]:
    base = Path(run_dir)
    return {
        "run_dir": base,
        "predictions": base / PREDICTIONS_FILENAME,
        "adjudication": base / ADJUDICATION_FILENAME,
        "summary_json": base / SUMMARY_JSON_FILENAME,
        "summary_md": base / SUMMARY_MD_FILENAME,
    }
