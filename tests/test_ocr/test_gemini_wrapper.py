import json
from io import BytesIO
from urllib import error

import numpy as np
import pytest

from southview.ocr.errors import OCRProviderError
from southview.ocr.gemini_wrapper import _api_key, _post_json, gemini_engine_version, run_gemini


def test_api_key_uses_configured_env(monkeypatch):
    monkeypatch.setattr(
        "southview.ocr.gemini_wrapper.get_config",
        lambda: {"ocr": {"gemini": {"api_key_env": "MY_GEMINI_KEY"}}},
    )
    monkeypatch.setenv("MY_GEMINI_KEY", "abc123")

    assert _api_key() == "abc123"


def test_api_key_falls_back_to_google_api_key(monkeypatch):
    monkeypatch.setattr(
        "southview.ocr.gemini_wrapper.get_config",
        lambda: {"ocr": {"gemini": {"api_key_env": "GEMINI_API_KEY"}}},
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-fallback-key")

    assert _api_key() == "google-fallback-key"


def test_api_key_missing_raises_clear_error(monkeypatch):
    monkeypatch.setattr(
        "southview.ocr.gemini_wrapper.get_config",
        lambda: {"ocr": {"gemini": {"api_key_env": "GEMINI_API_KEY"}}},
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="environment variable GEMINI_API_KEY is not set"):
        _api_key()


def test_gemini_engine_version_from_config(monkeypatch):
    monkeypatch.setattr(
        "southview.ocr.gemini_wrapper.get_config",
        lambda: {"ocr": {"gemini": {"model": "gemini-2.0-flash"}}},
    )

    assert gemini_engine_version() == "gemini:gemini-2.0-flash"


def test_run_gemini_returns_full_normalized_field_map(monkeypatch):
    payload_text = json.dumps(
        {
            "raw_text": "AARON, Benjamin L.\\nDate of Death December 8, 2004",
            "card_confidence": 0.91,
            "fields": {
                "deceased_name": "  AARON, Benjamin L.  ",
                "date_of_death": " December 8, 2004 ",
                "grave_fee": "",
            },
        }
    )

    monkeypatch.setattr(
        "southview.ocr.gemini_wrapper._post_json",
        lambda _payload: {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": payload_text}],
                    }
                }
            ]
        },
    )

    result = run_gemini(np.zeros((4, 4, 3), dtype=np.uint8))

    assert result["raw_text"] == "AARON, Benjamin L.\\nDate of Death December 8, 2004"
    assert result["card_confidence"] == pytest.approx(0.91)
    assert result["fields"]["deceased_name"] == "AARON, Benjamin L."
    assert result["fields"]["date_of_death"] == "December 8, 2004"
    assert result["fields"]["grave_fee"] is None
    # Missing keys in model output are still represented explicitly as nullable fields.
    assert result["fields"]["date_of_burial"] is None
    assert result["fields"]["undertaker"] is None


def test_run_gemini_invalid_json_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(
        "southview.ocr.gemini_wrapper._post_json",
        lambda _payload: {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "{bad json"}],
                    }
                }
            ]
        },
    )

    with pytest.raises(RuntimeError, match="invalid JSON"):
        run_gemini(np.zeros((2, 2, 3), dtype=np.uint8))


def test_post_json_retries_retryable_http_errors(monkeypatch):
    attempts = {"count": 0}
    sleep_calls: list[float] = []

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"ok": true}'

    def flaky_urlopen(_req, timeout):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise error.HTTPError(
                url="https://example.test",
                code=429,
                msg="Too Many Requests",
                hdrs=None,
                fp=BytesIO(b"RESOURCE_EXHAUSTED"),
            )
        return _FakeResponse()

    monkeypatch.setattr(
        "southview.ocr.gemini_wrapper.get_config",
        lambda: {
            "ocr": {
                "gemini": {
                    "max_retries": 2,
                    "retry_backoff_seconds": 0.5,
                    "retry_jitter_seconds": 0.0,
                }
            }
        },
    )
    monkeypatch.setattr("southview.ocr.gemini_wrapper._api_key", lambda: "key")
    monkeypatch.setattr("southview.ocr.gemini_wrapper.request.urlopen", flaky_urlopen)
    monkeypatch.setattr("southview.ocr.gemini_wrapper.time.sleep", sleep_calls.append)

    payload = _post_json({"hello": "world"})

    assert payload == {"ok": True}
    assert attempts["count"] == 3
    assert sleep_calls == [0.5, 1.0]


def test_post_json_raises_after_retry_exhaustion_for_url_errors(monkeypatch):
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        "southview.ocr.gemini_wrapper.get_config",
        lambda: {
            "ocr": {
                "gemini": {
                    "max_retries": 2,
                    "retry_backoff_seconds": 0.25,
                    "retry_jitter_seconds": 0.0,
                }
            }
        },
    )
    monkeypatch.setattr("southview.ocr.gemini_wrapper._api_key", lambda: "key")
    monkeypatch.setattr(
        "southview.ocr.gemini_wrapper.request.urlopen",
        lambda _req, timeout: (_ for _ in ()).throw(error.URLError("network down")),
    )
    monkeypatch.setattr("southview.ocr.gemini_wrapper.time.sleep", sleep_calls.append)

    with pytest.raises(OCRProviderError, match="network down"):
        _post_json({"hello": "world"})

    assert sleep_calls == [0.25, 0.5]
