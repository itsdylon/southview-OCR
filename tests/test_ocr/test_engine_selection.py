from southview.ocr.engine import get_ocr_engine_version, run_ocr, uses_rotation_sweep


def test_run_ocr_uses_gemini(monkeypatch):
    monkeypatch.setattr(
        "southview.ocr.engine.get_config",
        lambda: {"ocr": {"engine": "gemini", "gemini": {"model": "gemini-2.0-flash", "try_rotations": False}}},
    )
    monkeypatch.setattr(
        "southview.ocr.gemini_wrapper.get_config",
        lambda: {"ocr": {"gemini": {"model": "gemini-2.0-flash"}}},
    )
    monkeypatch.setattr(
        "southview.ocr.engine.run_gemini",
        lambda image: {"raw_text": "ok", "words": []},
    )

    result = run_ocr(image=None)

    assert result["raw_text"] == "ok"
    assert get_ocr_engine_version() == "gemini:gemini-2.0-flash"
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
