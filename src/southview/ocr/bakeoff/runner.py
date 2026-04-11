from __future__ import annotations

from pathlib import Path

from southview.ocr.bakeoff.artifacts import (
    default_run_paths,
    read_adjudication_csv,
    read_predictions_csv,
    write_adjudication_csv,
    write_predictions_csv,
    write_summary_json,
)
from southview.ocr.bakeoff.dataset import load_manifest
from southview.ocr.bakeoff.providers import ALL_MODEL_IDS, ModelRouter
from southview.ocr.bakeoff.scoring import (
    build_prediction_record,
    render_summary_markdown,
    summarize_predictions,
)


def run_bakeoff(
    *,
    manifest_path: str | Path,
    out_dir: str | Path,
    model_ids: list[str] | None = None,
    router: ModelRouter | None = None,
) -> dict:
    models = list(model_ids or ALL_MODEL_IDS)
    if not models:
        raise ValueError("No models provided for bake-off")

    cards = load_manifest(manifest_path)
    resolved_paths = default_run_paths(out_dir)
    resolved_paths["run_dir"].mkdir(parents=True, exist_ok=True)

    engine = router or ModelRouter()

    predictions = []
    for card in cards:
        for model_id in models:
            result = engine.run_model(model_id, card.image_path)
            predictions.append(
                build_prediction_record(card, model_id=model_id, result=result)
            )

    write_predictions_csv(resolved_paths["predictions"], predictions)
    write_adjudication_csv(resolved_paths["adjudication"], predictions)

    summary = summarize_predictions(predictions)
    summary.update(
        {
            "run_dir": str(resolved_paths["run_dir"].resolve()),
            "manifest_path": str(Path(manifest_path).resolve()),
            "cards_evaluated": len(cards),
            "models_requested": models,
        }
    )

    write_summary_json(resolved_paths["summary_json"], summary)
    resolved_paths["summary_md"].write_text(
        render_summary_markdown(summary), encoding="utf-8"
    )

    return {
        "run_dir": str(resolved_paths["run_dir"]),
        "predictions_csv": str(resolved_paths["predictions"]),
        "adjudication_csv": str(resolved_paths["adjudication"]),
        "summary_json": str(resolved_paths["summary_json"]),
        "summary_md": str(resolved_paths["summary_md"]),
        "summary": summary,
    }


def summarize_bakeoff(
    *,
    run_dir: str | Path,
    adjudication_path: str | Path | None = None,
) -> dict:
    paths = default_run_paths(run_dir)

    predictions = read_predictions_csv(paths["predictions"])

    adjudications = None
    if adjudication_path:
        adjudications = read_adjudication_csv(adjudication_path)
    elif paths["adjudication"].exists():
        adjudications = read_adjudication_csv(paths["adjudication"])

    summary = summarize_predictions(predictions, adjudications=adjudications)
    summary.update(
        {
            "run_dir": str(paths["run_dir"].resolve()),
            "predictions_csv": str(paths["predictions"].resolve()),
            "adjudication_csv": str(
                Path(adjudication_path).resolve()
                if adjudication_path
                else paths["adjudication"].resolve()
            ),
            "cards_evaluated": len({(p.card_id) for p in predictions}),
            "rows_scored": len(predictions),
        }
    )

    write_summary_json(paths["summary_json"], summary)
    paths["summary_md"].write_text(render_summary_markdown(summary), encoding="utf-8")

    return {
        "run_dir": str(paths["run_dir"]),
        "summary_json": str(paths["summary_json"]),
        "summary_md": str(paths["summary_md"]),
        "summary": summary,
    }
