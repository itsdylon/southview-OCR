from __future__ import annotations

import base64
import json
import os
import random
import re
import time
from typing import Any
from urllib import error, request

import cv2
import numpy as np

from southview.config import get_config
from southview.ocr.errors import OCRProviderError

_DEFAULT_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta"

_SYSTEM_INSTRUCTION = (
    "You extract text and structured fields from historical cemetery burial cards. "
    "Return strict JSON only."
)

CANONICAL_FIELDS = [
    "deceased_name",
    "address",
    "owner",
    "relation",
    "phone",
    "date_of_death",
    "date_of_burial",
    "description",
    "sex",
    "age",
    "grave_type",
    "grave_fee",
    "undertaker",
    "board_of_health_no",
    "svc_no",
]

_PROMPT = """
Read this cemetery burial card image and return JSON with:
- raw_text: a faithful transcription of visible card text, preserving line breaks where practical.
- card_confidence: a number from 0.0 to 1.0 for overall extraction confidence.
- fields: an object with these keys (all nullable strings):
  deceased_name, address, owner, relation, phone,
  date_of_death, date_of_burial, description,
  sex, age, grave_type, grave_fee,
  undertaker, board_of_health_no, svc_no.

Field guidance:
- deceased_name: top unlabeled deceased name text.
- address: top unlabeled address text.
- owner/relation/phone: values near those labels when present.
- date_of_death/date_of_burial: preserve exact visible date text.
- description: grave location/description text.
- grave_type: value for type of grave.

Rules:
- Do not invent values.
- Use only values explicitly visible on the card.
- If a field is missing or illegible, return null for that field.
- Output valid JSON only.
""".strip()

_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "raw_text": {"type": "STRING"},
        "card_confidence": {"type": "NUMBER"},
        "fields": {
            "type": "OBJECT",
            "properties": {
                field: {"type": "STRING", "nullable": True}
                for field in CANONICAL_FIELDS
            },
        },
    },
    "required": ["raw_text", "card_confidence", "fields"],
}


def _gemini_config() -> dict[str, Any]:
    return get_config().get("ocr", {}).get("gemini", {})


def _api_key() -> str:
    cfg = _gemini_config()
    env_name = str(cfg.get("api_key_env", "GEMINI_API_KEY")).strip() or "GEMINI_API_KEY"
    value = os.getenv(env_name, "").strip()
    if not value and env_name == "GEMINI_API_KEY":
        value = os.getenv("GOOGLE_API_KEY", "").strip()
    if not value:
        raise OCRProviderError(
            f"Google AI OCR is enabled, but environment variable {env_name} is not set."
        )
    return value


def _model_name() -> str:
    return str(_gemini_config().get("model", "gemini-2.5-flash")).strip()


def gemini_engine_version() -> str:
    return f"gemini:{_model_name()}"


def _endpoint_url() -> str:
    base = str(_gemini_config().get("endpoint", _DEFAULT_ENDPOINT)).rstrip("/")
    return f"{base}/models/{_model_name()}:generateContent"


def _timeout_seconds() -> float:
    return float(_gemini_config().get("timeout_seconds", 30))


def _max_retries() -> int:
    return max(0, int(_gemini_config().get("max_retries", 3)))


def _retry_backoff_seconds() -> float:
    return max(0.0, float(_gemini_config().get("retry_backoff_seconds", 1.0)))


def _retry_jitter_seconds() -> float:
    return max(0.0, float(_gemini_config().get("retry_jitter_seconds", 0.25)))


def _extract_text_part(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no candidates.")

    parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
    texts = [
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and part.get("text")
    ]
    if not texts:
        raise RuntimeError("Gemini response did not include text content.")
    return "".join(texts).strip()


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_json_text(text: str) -> str:
    cleaned = _strip_code_fences(text)
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1].strip()
    return cleaned


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_fields(raw_fields: Any) -> dict[str, str | None]:
    payload = raw_fields if isinstance(raw_fields, dict) else {}
    normalized: dict[str, str | None] = {}
    for key in CANONICAL_FIELDS:
        normalized[key] = _normalize_optional_text(payload.get(key))
    return normalized


def _normalize_result(data: dict[str, Any]) -> dict[str, Any]:
    raw_text = str(data.get("raw_text") or "").strip()

    try:
        card_confidence = float(data.get("card_confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        card_confidence = 0.0
    card_confidence = max(0.0, min(1.0, card_confidence))

    return {
        "raw_text": raw_text,
        "words": [],
        "card_confidence": card_confidence,
        "fields": _normalize_fields(data.get("fields")),
    }


def _retry_delay_seconds(attempt: int) -> float:
    base_delay = _retry_backoff_seconds() * (2 ** max(attempt - 1, 0))
    jitter = _retry_jitter_seconds()
    if jitter > 0:
        base_delay += random.uniform(0.0, jitter)
    return base_delay


def _is_retryable_http_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600


def _post_json(payload: dict[str, Any]) -> dict[str, Any]:
    api_key = _api_key()
    env_name = str(_gemini_config().get("api_key_env", "GEMINI_API_KEY")).strip() or "GEMINI_API_KEY"
    for attempt in range(_max_retries() + 1):
        req = request.Request(
            _endpoint_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=_timeout_seconds()) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if "API_KEY_INVALID" in detail or "API Key not found" in detail:
                raise OCRProviderError(
                    "Google AI OCR API key was rejected. "
                    f"Checked env var: {env_name} (len={len(api_key)}). "
                    "Verify the key belongs to the intended AI Studio project and "
                    "that API/Application restrictions allow Generative Language API calls."
                ) from exc
            if attempt < _max_retries() and _is_retryable_http_status(exc.code):
                time.sleep(_retry_delay_seconds(attempt + 1))
                continue
            raise OCRProviderError(
                f"Google AI OCR request failed: HTTP {exc.code} {detail}"
            ) from exc
        except error.URLError as exc:
            if attempt < _max_retries():
                time.sleep(_retry_delay_seconds(attempt + 1))
                continue
            raise OCRProviderError(f"Google AI OCR request failed: {exc.reason}") from exc


def parse_structured_fields_with_gemini(raw_text: str) -> dict[str, Any]:
    """
    Legacy helper kept for compatibility.
    Production extraction should use run_gemini single-pass output.
    """
    if not raw_text.strip():
        return {}
    return {}


def run_gemini(image: np.ndarray) -> dict[str, Any]:
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Could not encode image for Google AI OCR request.")

    payload = {
        "systemInstruction": {
            "parts": [{"text": _SYSTEM_INSTRUCTION}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": _PROMPT},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": base64.b64encode(encoded.tobytes()).decode("ascii"),
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": _RESPONSE_SCHEMA,
        },
    }

    body = _post_json(payload)
    text = _extract_text_part(body)
    try:
        parsed = json.loads(_extract_json_text(text))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Google AI OCR returned invalid JSON: {text}") from exc

    return _normalize_result(parsed)
