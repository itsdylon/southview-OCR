from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone

from southview.ocr.bakeoff.normalize import normalize_date, normalize_name
from southview.ocr.bakeoff.types import AdjudicationRecord, ManifestRecord, PredictionRecord, ProviderResult


def build_prediction_record(
    card: ManifestRecord,
    *,
    model_id: str,
    result: ProviderResult,
) -> PredictionRecord:
    gt_name = card.deceased_name or ""
    gt_dod = card.date_of_death or ""
    pred_name = (result.deceased_name or "").strip()
    pred_dod = normalize_date(result.date_of_death or "", strict=False)

    norm_gt_name = normalize_name(gt_name)
    norm_gt_dod = normalize_date(gt_dod, strict=False)
    norm_pred_name = normalize_name(pred_name)
    norm_pred_dod = normalize_date(pred_dod, strict=False)

    if result.error:
        name_match = False
        dod_match = False
    else:
        name_match = norm_gt_name == norm_pred_name
        dod_match = norm_gt_dod == norm_pred_dod

    usage_json = "{}"
    try:
        usage_json = json.dumps(result.usage or {}, ensure_ascii=False, sort_keys=True)
    except Exception:
        usage_json = "{}"

    return PredictionRecord(
        card_id=card.card_id,
        image_path=card.image_path,
        difficulty_bucket=card.difficulty_bucket,
        model_id=model_id,
        gt_deceased_name=gt_name,
        gt_date_of_death=gt_dod,
        pred_deceased_name=pred_name,
        pred_date_of_death=pred_dod,
        normalized_gt_name=norm_gt_name,
        normalized_gt_dod=norm_gt_dod,
        normalized_pred_name=norm_pred_name,
        normalized_pred_dod=norm_pred_dod,
        name_match=name_match,
        dod_match=dod_match,
        exact_match=name_match and dod_match,
        latency_ms=float(result.latency_ms or 0.0),
        error=result.error or "",
        usage_json=usage_json,
        raw_text=result.raw_text or "",
    )


def prediction_to_dict(record: PredictionRecord) -> dict[str, str]:
    data = asdict(record)
    out: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, bool):
            out[key] = "true" if value else "false"
        else:
            out[key] = str(value)
    return out


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = max(0.0, min(1.0, quantile)) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _summarize_bucket_rows(rows: list[dict]) -> dict[str, float | int]:
    total = len(rows)
    name_correct = sum(1 for r in rows if r["final_name_match"])
    dod_correct = sum(1 for r in rows if r["final_dod_match"])
    exact_correct = sum(1 for r in rows if r["final_exact_match"])
    errors = sum(1 for r in rows if r["error"])
    roundtrip_ms = [float(r["latency_ms"]) for r in rows]
    total_roundtrip_ms = sum(roundtrip_ms)
    avg_roundtrip_ms = (total_roundtrip_ms / total) if total else 0.0

    return {
        "cards_total": total,
        "name_accuracy": _rate(name_correct, total),
        "dod_accuracy": _rate(dod_correct, total),
        "exact_accuracy": _rate(exact_correct, total),
        "error_count": errors,
        "error_rate": _rate(errors, total),
        # `avg_latency_ms` is kept for backwards compatibility.
        "avg_latency_ms": avg_roundtrip_ms,
        "avg_roundtrip_ms": avg_roundtrip_ms,
        "p50_roundtrip_ms": _percentile(roundtrip_ms, 0.50),
        "p95_roundtrip_ms": _percentile(roundtrip_ms, 0.95),
        "min_roundtrip_ms": min(roundtrip_ms) if roundtrip_ms else 0.0,
        "max_roundtrip_ms": max(roundtrip_ms) if roundtrip_ms else 0.0,
        "total_roundtrip_ms": total_roundtrip_ms,
    }


def summarize_predictions(
    predictions: list[PredictionRecord],
    *,
    adjudications: list[AdjudicationRecord] | None = None,
) -> dict:
    adjudication_map: dict[tuple[str, str], AdjudicationRecord] = {}
    for adj in adjudications or []:
        adjudication_map[(adj.card_id, adj.model_id)] = adj

    scored_rows: list[dict] = []
    for p in predictions:
        adj = adjudication_map.get((p.card_id, p.model_id))

        final_name_match = (
            adj.human_name_correct if adj and adj.human_name_correct is not None else p.name_match
        )
        final_dod_match = (
            adj.human_dod_correct if adj and adj.human_dod_correct is not None else p.dod_match
        )

        scored_rows.append(
            {
                "model_id": p.model_id,
                "difficulty_bucket": p.difficulty_bucket,
                "latency_ms": p.latency_ms,
                "error": p.error,
                "final_name_match": bool(final_name_match),
                "final_dod_match": bool(final_dod_match),
                "final_exact_match": bool(final_name_match and final_dod_match),
            }
        )

    by_model: dict[str, list[dict]] = defaultdict(list)
    for row in scored_rows:
        by_model[row["model_id"]].append(row)

    models_out: list[dict] = []
    for model_id in sorted(by_model):
        model_rows = by_model[model_id]
        model_summary = _summarize_bucket_rows(model_rows)

        by_bucket: dict[str, dict[str, float | int]] = {}
        grouped: dict[str, list[dict]] = defaultdict(list)
        for r in model_rows:
            grouped[r["difficulty_bucket"]].append(r)

        for bucket in sorted(grouped):
            by_bucket[bucket] = _summarize_bucket_rows(grouped[bucket])

        models_out.append(
            {
                "model_id": model_id,
                **model_summary,
                "by_difficulty": by_bucket,
            }
        )

    ranking = sorted(
        [
            {
                "model_id": m["model_id"],
                "exact_accuracy": m["exact_accuracy"],
                "name_accuracy": m["name_accuracy"],
                "dod_accuracy": m["dod_accuracy"],
                "error_count": m["error_count"],
                "avg_roundtrip_ms": m["avg_roundtrip_ms"],
                "p95_roundtrip_ms": m["p95_roundtrip_ms"],
            }
            for m in models_out
        ],
        key=lambda x: (
            -x["exact_accuracy"],
            -x["name_accuracy"],
            -x["dod_accuracy"],
            x["error_count"],
            x["avg_roundtrip_ms"],
            x["model_id"],
        ),
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models": models_out,
        "ranking": ranking,
        "adjudication_applied": bool(adjudications),
    }


def render_summary_markdown(summary: dict) -> str:
    lines: list[str] = []
    lines.append("# Southview OCR Bake-Off Summary")
    lines.append("")
    lines.append(f"Generated: {summary['generated_at']}")
    lines.append("")
    lines.append("## Ranking")
    lines.append("")
    lines.append("| Rank | Model | Exact | Name | DoD | Errors | Avg RT (ms) | P95 RT (ms) |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")

    for idx, row in enumerate(summary.get("ranking", []), start=1):
        lines.append(
            (
                "| {rank} | {model} | {exact:.2%} | {name:.2%} | {dod:.2%} | "
                "{errors} | {avg_rt:.1f} | {p95_rt:.1f} |"
            ).format(
                rank=idx,
                model=row["model_id"],
                exact=row["exact_accuracy"],
                name=row["name_accuracy"],
                dod=row["dod_accuracy"],
                errors=row["error_count"],
                avg_rt=row.get("avg_roundtrip_ms", 0.0),
                p95_rt=row.get("p95_roundtrip_ms", 0.0),
            )
        )

    lines.append("")
    lines.append("## Per-Model Buckets")
    lines.append("")

    for model in summary.get("models", []):
        lines.append(f"### {model['model_id']}")
        lines.append("")
        lines.append(
            (
                "Overall: exact={exact:.2%}, name={name:.2%}, dod={dod:.2%}, "
                "errors={errors}/{total} ({error_rate:.2%}), "
                "roundtrip avg={avg_rt:.1f}ms p50={p50_rt:.1f}ms p95={p95_rt:.1f}ms"
            ).format(
                exact=model["exact_accuracy"],
                name=model["name_accuracy"],
                dod=model["dod_accuracy"],
                errors=model["error_count"],
                total=model["cards_total"],
                error_rate=model["error_rate"],
                avg_rt=model.get("avg_roundtrip_ms", 0.0),
                p50_rt=model.get("p50_roundtrip_ms", 0.0),
                p95_rt=model.get("p95_roundtrip_ms", 0.0),
            )
        )
        lines.append("")
        lines.append("| Bucket | Exact | Name | DoD | Errors | Error Rate | N |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        by_difficulty = model.get("by_difficulty", {})
        for bucket in sorted(by_difficulty):
            b = by_difficulty[bucket]
            lines.append(
                "| {bucket} | {exact:.2%} | {name:.2%} | {dod:.2%} | {errors} | {error_rate:.2%} | {total} |".format(
                    bucket=bucket,
                    exact=b["exact_accuracy"],
                    name=b["name_accuracy"],
                    dod=b["dod_accuracy"],
                    errors=b["error_count"],
                    error_rate=b["error_rate"],
                    total=b["cards_total"],
                )
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"
