import numpy as np

from southview.ocr.processor_min import _orientation_score, _rotation_candidates, process_card_min


def test_process_card_min_uses_gemini_text_without_word_boxes(monkeypatch):
    monkeypatch.setattr(
        "southview.ocr.processor_min.get_ocr_engine_name",
        lambda: "gemini",
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.uses_rotation_sweep",
        lambda: False,
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.get_ocr_engine_version",
        lambda: "gemini:gemini-2.0-flash",
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.cv2.imread",
        lambda path: np.zeros((4, 4, 3), dtype=np.uint8),
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.preprocess_array",
        lambda img: img,
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.run_ocr",
        lambda img: {
            "raw_text": "PARKS, Carl\nDate of Death October 16, 2021",
            "words": [],
            "card_confidence": 0.92,
        },
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.parse_structured_fields_with_gemini",
        lambda raw_text: {},
    )

    result = process_card_min("fake.png")

    assert result["fields"]["owner_name"] == "PARKS, Carl"
    assert result["fields"]["date_of_death"] == "2021-10-16"
    assert result["orientation"] == 0
    assert result["meta"]["ocr_engine_version"] == "gemini:gemini-2.0-flash"
    assert result["card_confidence"] > 0.70


def test_process_card_min_runs_structured_fallback_once_after_rotation_selection(monkeypatch):
    calls = {"ocr": 0, "fallback": 0}

    monkeypatch.setattr(
        "southview.ocr.processor_min.get_ocr_engine_name",
        lambda: "gemini",
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.uses_rotation_sweep",
        lambda: True,
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.get_ocr_engine_version",
        lambda: "gemini:gemini-2.0-flash",
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min._rotation_candidates",
        lambda: [(90, 1), (270, 2)],
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.cv2.imread",
        lambda path: np.zeros((4, 4, 3), dtype=np.uint8),
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.cv2.rotate",
        lambda img, flag: img,
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.preprocess_array",
        lambda img: img,
    )

    def fake_run_ocr(img):
        calls["ocr"] += 1
        if calls["ocr"] == 1:
            return {"raw_text": "garbled text", "words": [], "card_confidence": 0.25}
        return {
            "raw_text": "ADAMS, James\nDate of Death 3-20-41",
            "words": [],
            "card_confidence": 0.88,
        }

    monkeypatch.setattr("southview.ocr.processor_min.run_ocr", fake_run_ocr)

    def fake_fallback(raw_text):
        calls["fallback"] += 1
        return {"owner_name": "OVERRIDE, WRONG"}

    monkeypatch.setattr(
        "southview.ocr.processor_min.parse_structured_fields_with_gemini",
        fake_fallback,
    )

    result = process_card_min("fake.png")

    assert calls["ocr"] == 2
    assert calls["fallback"] == 1
    assert result["orientation"] == 270
    assert result["fields"]["owner_name"] == "ADAMS, James"


def test_rotation_candidates_default_to_all_for_gemini(monkeypatch):
    monkeypatch.setattr(
        "southview.ocr.processor_min.get_ocr_engine_name",
        lambda: "gemini",
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.get_config",
        lambda: {"ocr": {"gemini": {}}},
    )

    assert [degree for degree, _ in _rotation_candidates()] == [0, 90, 180, 270]


def test_orientation_score_uses_card_confidence_when_words_missing():
    parsed = {
        "owner_name": {"value": "AARON, Benjamin L.", "support": []},
        "date_of_death": {"value": "2004-12-08", "support": []},
    }

    better = _orientation_score(
        parsed,
        [],
        "AARON, Benjamin L.\nDate of death: December 8, 2004",
        {"card_confidence": 0.82},
    )
    worse = _orientation_score(
        {"owner_name": {"value": None, "support": []}},
        [],
        "garbled text",
        {"card_confidence": 0.3},
    )

    assert better > worse
