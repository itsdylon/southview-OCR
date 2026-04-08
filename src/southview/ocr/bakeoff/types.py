from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ManifestRecord:
    card_id: str
    image_path: str
    difficulty_bucket: str
    deceased_name: str
    date_of_death: str


@dataclass
class ProviderResult:
    deceased_name: str = ""
    date_of_death: str = ""
    raw_text: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    error: str = ""


@dataclass
class PredictionRecord:
    card_id: str
    image_path: str
    difficulty_bucket: str
    model_id: str
    gt_deceased_name: str
    gt_date_of_death: str
    pred_deceased_name: str
    pred_date_of_death: str
    normalized_gt_name: str
    normalized_gt_dod: str
    normalized_pred_name: str
    normalized_pred_dod: str
    name_match: bool
    dod_match: bool
    exact_match: bool
    latency_ms: float
    error: str
    usage_json: str
    raw_text: str


@dataclass
class AdjudicationRecord:
    card_id: str
    model_id: str
    human_name_correct: bool | None
    human_dod_correct: bool | None
    adjudication_notes: str
