import sys
import types

import pytest
from PIL import Image

from southview.ocr.bakeoff.providers import (
    GeminiProvider,
    OpenAIResponsesProvider,
    parse_extraction_payload,
)


def _write_png(path):
    image = Image.new("RGB", (8, 8), (255, 255, 255))
    image.save(path)


def _install_fake_google_genai(monkeypatch):
    fake_google = types.ModuleType("google")
    fake_genai = types.ModuleType("google.genai")

    class _FakeClient:
        def __init__(self, *, api_key):
            self.api_key = api_key

    fake_genai.Client = _FakeClient
    fake_google.genai = fake_genai

    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    return _FakeClient


def _install_fake_google_genai_types(monkeypatch):
    fake_types = types.ModuleType("google.genai.types")

    class _Part:
        @staticmethod
        def from_text(*, text: str):
            return {"kind": "text", "text": text}

        @staticmethod
        def from_bytes(*, data: bytes, mime_type: str):
            return {"kind": "bytes", "size": len(data), "mime_type": mime_type}

    class _GenerateContentConfig:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    fake_types.Part = _Part
    fake_types.GenerateContentConfig = _GenerateContentConfig

    fake_genai = sys.modules.get("google.genai")
    if fake_genai is None:
        fake_google = types.ModuleType("google")
        fake_genai = types.ModuleType("google.genai")
        fake_google.genai = fake_genai
        monkeypatch.setitem(sys.modules, "google", fake_google)
        monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    fake_genai.types = fake_types
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)


def test_parse_extraction_payload_valid_json():
    name, dod = parse_extraction_payload('{"deceased_name":"SMITH, John", "date_of_death":"2021-10-30"}')
    assert name == "SMITH, John"
    assert dod == "2021-10-30"


def test_parse_extraction_payload_embedded_json():
    raw = "```json\n{\"deceased_name\":\"SMITH, John\",\"date_of_death\":\"\"}\n```"
    name, dod = parse_extraction_payload(raw)
    assert name == "SMITH, John"
    assert dod == ""


def test_openai_provider_returns_error_row_on_api_failure(tmp_path):
    image_path = tmp_path / "card.png"
    _write_png(image_path)

    class _FailingResponses:
        def create(self, **kwargs):
            raise RuntimeError("forced openai failure")

    class _FailingClient:
        responses = _FailingResponses()

    provider = OpenAIResponsesProvider(client=_FailingClient())
    out = provider.run_model("gpt-4.1-mini", str(image_path))

    assert out.error
    assert "forced openai failure" in out.error
    assert out.deceased_name == ""
    assert out.date_of_death == ""
    assert out.latency_ms >= 0.0


def test_gemini_provider_accepts_google_api_key_env(monkeypatch):
    fake_client_cls = _install_fake_google_genai(monkeypatch)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key-123")

    provider = GeminiProvider()
    client = provider._get_client()

    assert isinstance(client, fake_client_cls)
    assert client.api_key == "google-key-123"


def test_gemini_provider_missing_api_key_has_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    provider = GeminiProvider()
    with pytest.raises(RuntimeError, match="Set GEMINI_API_KEY or GOOGLE_API_KEY"):
        provider._get_client()


def test_gemini_provider_builds_generate_content_request(tmp_path, monkeypatch):
    image_path = tmp_path / "card.png"
    _write_png(image_path)
    _install_fake_google_genai_types(monkeypatch)

    class _FakeModels:
        def __init__(self):
            self.calls = []

        def generate_content(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "text": '{"deceased_name":"DOE, Jane", "date_of_death":"2020-01-05"}',
                "usage_metadata": {"prompt_token_count": 11, "candidates_token_count": 4},
            }

    class _FakeClient:
        def __init__(self):
            self.models = _FakeModels()

    provider = GeminiProvider(client=_FakeClient())
    out = provider.run_model("gemini-2.0-flash", str(image_path))

    assert out.error == ""
    assert out.deceased_name == "DOE, Jane"
    assert out.date_of_death == "2020-01-05"
    assert out.usage["prompt_token_count"] == 11

    call = provider._client.models.calls[0]
    assert call["model"] == "gemini-2.0-flash"
    assert len(call["contents"]) == 2
    assert call["contents"][0]["kind"] == "text"
    assert call["contents"][1]["kind"] == "bytes"
    assert call["contents"][1]["mime_type"] == "image/png"
    assert call["config"].temperature == 0
    assert call["config"].response_mime_type == "application/json"
