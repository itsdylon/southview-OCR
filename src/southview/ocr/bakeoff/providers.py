from __future__ import annotations

import base64
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from southview.ocr.bakeoff.types import ProviderResult

OPENAI_MODEL_IDS = {"gpt-4.1-mini", "gpt-4o"}
GEMINI_MODEL_IDS = {"gemini-2.0-flash"}

ALL_MODEL_IDS = ["gpt-4.1-mini", "gemini-2.0-flash", "gpt-4o"]

_EXTRACTION_PROMPT = (
    "Extract the following fields from this Southview cemetery card image. "
    "Return ONLY valid JSON with exactly these keys: "
    '{"deceased_name":"", "date_of_death":""}. '
    "Rules: if a value is missing or unreadable, return an empty string. "
    "For date_of_death, return YYYY-MM-DD when possible; otherwise empty string."
)

_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "deceased_name": {"type": "string"},
        "date_of_death": {"type": "string"},
    },
    "required": ["deceased_name", "date_of_death"],
    "additionalProperties": False,
}


def _mime_type_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    # Default keeps adapters functional for odd extensions.
    return "application/octet-stream"


def _response_to_dict(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if hasattr(response, "to_dict"):
        return response.to_dict()
    return {}


def _coerce_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {"raw": str(dumped)}
    if hasattr(value, "to_dict"):
        dumped = value.to_dict()
        return dumped if isinstance(dumped, dict) else {"raw": str(dumped)}
    return {"raw": str(value)}


def _extract_json_candidate(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("Model returned empty output")

    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if match:
        return match.group(0)

    raise ValueError("Model output did not contain a JSON object")


def parse_extraction_payload(raw_text: str) -> tuple[str, str]:
    json_candidate = _extract_json_candidate(raw_text)
    payload = json.loads(json_candidate)
    if not isinstance(payload, dict):
        raise ValueError("Model output JSON was not an object")

    if "deceased_name" not in payload or "date_of_death" not in payload:
        raise ValueError("Model output missing required keys")

    deceased_name = str(payload.get("deceased_name") or "").strip()
    date_of_death = str(payload.get("date_of_death") or "").strip()
    return deceased_name, date_of_death


def _extract_openai_text(payload: dict[str, Any]) -> str:
    if payload.get("output_text"):
        return str(payload.get("output_text"))

    chunks: list[str] = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text")
            if text:
                chunks.append(str(text))
    return "\n".join(chunks).strip()


def _extract_gemini_text(payload: dict[str, Any]) -> str:
    if payload.get("text"):
        return str(payload["text"])

    chunks: list[str] = []
    for candidate in payload.get("candidates", []) or []:
        content = candidate.get("content", {}) or {}
        for part in content.get("parts", []) or []:
            text = part.get("text")
            if text:
                chunks.append(str(text))
    return "\n".join(chunks).strip()


class OpenAIResponsesProvider:
    def __init__(self, *, api_key: str | None = None, client: Any = None) -> None:
        self._api_key = api_key
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        api_key = self._api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI adapter requires the 'openai' package. Install project dependencies first."
            ) from exc

        self._client = OpenAI(api_key=api_key)
        return self._client

    def run_model(self, model_id: str, image_path: str) -> ProviderResult:
        if model_id not in OPENAI_MODEL_IDS:
            raise ValueError(f"Unsupported OpenAI model: {model_id}")

        start = time.perf_counter()
        raw_text = ""
        usage: dict[str, Any] = {}

        try:
            client = self._get_client()
            path = Path(image_path)
            mime_type = _mime_type_for_path(path)
            image_bytes = path.read_bytes()
            data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"

            response = client.responses.create(
                model=model_id,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": _EXTRACTION_PROMPT},
                            {"type": "input_image", "image_url": data_url},
                        ],
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "southview_bakeoff_fields",
                        "schema": _RESPONSE_SCHEMA,
                        "strict": True,
                    }
                },
            )

            payload = _response_to_dict(response)
            raw_text = _extract_openai_text(payload)
            usage = _coerce_dict(payload.get("usage"))
            deceased_name, date_of_death = parse_extraction_payload(raw_text)

            return ProviderResult(
                deceased_name=deceased_name,
                date_of_death=date_of_death,
                raw_text=raw_text,
                usage=usage,
                latency_ms=(time.perf_counter() - start) * 1000.0,
            )

        except Exception as exc:
            return ProviderResult(
                raw_text=raw_text,
                usage=usage,
                latency_ms=(time.perf_counter() - start) * 1000.0,
                error=str(exc),
            )


class GeminiProvider:
    def __init__(self, *, api_key: str | None = None, client: Any = None) -> None:
        self._api_key = api_key
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        api_key = self._api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")

        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError(
                "Gemini adapter requires the 'google-genai' package. Install project dependencies first."
            ) from exc

        self._client = genai.Client(api_key=api_key)
        return self._client

    def run_model(self, model_id: str, image_path: str) -> ProviderResult:
        if model_id not in GEMINI_MODEL_IDS:
            raise ValueError(f"Unsupported Gemini model: {model_id}")

        start = time.perf_counter()
        raw_text = ""
        usage: dict[str, Any] = {}

        try:
            client = self._get_client()
            path = Path(image_path)
            mime_type = _mime_type_for_path(path)
            image_bytes = path.read_bytes()

            try:
                from google.genai import types
            except ImportError as exc:
                raise RuntimeError(
                    "Gemini adapter requires 'google.genai.types'. Update google-genai package."
                ) from exc

            response = client.models.generate_content(
                model=model_id,
                contents=[
                    types.Part.from_text(text=_EXTRACTION_PROMPT),
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ],
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=_RESPONSE_SCHEMA,
                ),
            )

            payload = _response_to_dict(response)
            raw_text = _extract_gemini_text(payload)
            usage = _coerce_dict(payload.get("usage_metadata") or payload.get("usage"))
            deceased_name, date_of_death = parse_extraction_payload(raw_text)

            return ProviderResult(
                deceased_name=deceased_name,
                date_of_death=date_of_death,
                raw_text=raw_text,
                usage=usage,
                latency_ms=(time.perf_counter() - start) * 1000.0,
            )

        except Exception as exc:
            return ProviderResult(
                raw_text=raw_text,
                usage=usage,
                latency_ms=(time.perf_counter() - start) * 1000.0,
                error=str(exc),
            )


class ModelRouter:
    def __init__(
        self,
        *,
        openai_provider: OpenAIResponsesProvider | None = None,
        gemini_provider: GeminiProvider | None = None,
    ) -> None:
        self._openai = openai_provider or OpenAIResponsesProvider()
        self._gemini = gemini_provider or GeminiProvider()

    def run_model(self, model_id: str, image_path: str) -> ProviderResult:
        if model_id in OPENAI_MODEL_IDS:
            return self._openai.run_model(model_id, image_path)
        if model_id in GEMINI_MODEL_IDS:
            return self._gemini.run_model(model_id, image_path)
        raise ValueError(f"Unsupported model id: {model_id}")
