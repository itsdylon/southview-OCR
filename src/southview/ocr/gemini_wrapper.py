from __future__ import annotations

import base64
import json
import os
import re
from typing import Any
from urllib import error, request

import cv2
import numpy as np

from southview.config import get_config

_DEFAULT_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta"

_SYSTEM_INSTRUCTION = (
    "You extract text from historical cemetery burial cards. "
    "Return strict JSON only."
)

_PROMPT = """
Read this cemetery burial card image and return JSON with:
- raw_text: a faithful transcription of the visible card text, preserving line breaks where practical.
- card_confidence: a number from 0.0 to 1.0 representing your overall confidence in the extraction.

Rules:
- Do not invent values.
- Focus on transcription, not field interpretation.
- Preserve field labels exactly when visible, including labels like Date of Death, Date of Burial, DOB, Undertaker, SVC No, Type of Grave, Grave Fee, and Board of Health No.
- If two nearby dates appear on separate lines, transcribe both lines separately. Do not collapse two different dates into one repeated date.
- Preserve numbers and punctuation as faithfully as possible, including commas inside numbers like 49,711 and separators in dates like 3-20-41.
- Output valid JSON only.
""".strip()

_STRUCTURED_PARSE_PROMPT = """
Given OCR text from a historical cemetery burial card, extract only the core structured fields and return JSON only.

Target fields:
- owner_name
- description
- sex
- age
- undertaker
- svc_no

Rules:
- Use only values explicitly present in the OCR text.
- Do not infer missing values.
- Ignore owner, relation, address, phone, grave fee, and board of health numbers even if they appear in the OCR text.
- If a field is not present, return null.
""".strip()

_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "raw_text": {"type": "STRING"},
        "card_confidence": {"type": "NUMBER"},
    },
    "required": ["raw_text", "card_confidence"],
}

_STRUCTURED_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "owner_name": {"type": "STRING", "nullable": True},
        "description": {"type": "STRING", "nullable": True},
        "sex": {"type": "STRING", "nullable": True},
        "age": {"type": "STRING", "nullable": True},
        "undertaker": {"type": "STRING", "nullable": True},
        "svc_no": {"type": "STRING", "nullable": True},
    },
}


def _gemini_config() -> dict[str, Any]:
    return get_config().get("ocr", {}).get("gemini", {})


def _api_key() -> str:
    cfg = _gemini_config()
    env_name = cfg.get("api_key_env", "GEMINI_API_KEY")
    value = os.getenv(env_name, "").strip()
    if not value:
        raise RuntimeError(
            f"Google AI OCR is enabled, but environment variable {env_name} is not set."
        )
    return value


def _model_name() -> str:
    return str(_gemini_config().get("model", "gemma-4-31b")).strip()


def gemini_engine_version() -> str:
    return f"gemini:{_model_name()}"


def _endpoint_url() -> str:
    base = str(_gemini_config().get("endpoint", _DEFAULT_ENDPOINT)).rstrip("/")
    return f"{base}/models/{_model_name()}:generateContent"


def _timeout_seconds() -> float:
    return float(_gemini_config().get("timeout_seconds", 30))


def _structured_fallback_enabled() -> bool:
    return bool(_gemini_config().get("structured_fallback", True))


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
    }


def _post_json(payload: dict[str, Any]) -> dict[str, Any]:
    req = request.Request(
        _endpoint_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": _api_key(),
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=_timeout_seconds()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google AI OCR request failed: HTTP {exc.code} {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Google AI OCR request failed: {exc.reason}") from exc


def parse_structured_fields_with_gemini(raw_text: str) -> dict[str, Any]:
    if not raw_text.strip() or not _structured_fallback_enabled():
        return {}

    payload = {
        "systemInstruction": {
            "parts": [{"text": _SYSTEM_INSTRUCTION}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": _STRUCTURED_PARSE_PROMPT},
                    {"text": raw_text},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": _STRUCTURED_RESPONSE_SCHEMA,
        },
    }

    body = _post_json(payload)
    text = _extract_text_part(body)
    try:
        parsed = json.loads(_extract_json_text(text))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Google AI OCR returned invalid JSON: {text}") from exc

    out: dict[str, Any] = {}
    for key, value in parsed.items():
        if value is None:
            out[key] = None
        else:
            text_value = str(value).strip()
            out[key] = text_value or None
    return out


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
