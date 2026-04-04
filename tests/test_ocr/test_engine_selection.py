from southview.ocr.engine import get_ocr_engine_version, run_ocr, uses_rotation_sweep


def test_run_ocr_uses_gemini(monkeypatch):
    monkeypatch.setattr(
        "southview.ocr.engine.get_config",
        lambda: {"ocr": {"engine": "gemini", "gemini": {"model": "gemma-4-31b"}}},
    )
    monkeypatch.setattr(
        "southview.ocr.engine.run_gemini",
        lambda image: {"raw_text": "ok", "words": []},
    )

    result = run_ocr(image=None)

    assert result["raw_text"] == "ok"
    assert get_ocr_engine_version() == "gemini:gemma-4-31b"
    assert uses_rotation_sweep() is False


def test_run_ocr_uses_tesseract(monkeypatch):
    monkeypatch.setattr(
        "southview.ocr.engine.get_config",
        lambda: {"ocr": {"engine": "tesseract"}},
    )
    monkeypatch.setattr(
        "southview.ocr.engine.run_tesseract",
        lambda image: {"raw_text": "ocr", "words": [{"conf": 90}]},
    )

    result = run_ocr(image=None)

    assert result["raw_text"] == "ocr"
    assert get_ocr_engine_version() == "tesseract"
    assert uses_rotation_sweep() is True
