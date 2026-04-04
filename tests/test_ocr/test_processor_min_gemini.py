import numpy as np

from southview.ocr.processor_min import _orientation_score, _rotation_candidates, _template_order_score, process_card_min


def test_process_card_min_uses_llm_fields_without_rotation(monkeypatch):
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
        lambda: "gemini:gemma-4-31b",
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
    assert result["card_confidence"] > 0.70
    assert result["field_confidence"]["owner_name"] <= 0.82
    assert result["field_confidence"]["date_of_death"] <= 0.82
    assert result["orientation"] == 0
    assert result["meta"]["ocr_engine_version"] == "gemini:gemma-4-31b"


def test_process_card_min_uses_gemini_structured_fallback_only_for_missing_fields(monkeypatch):
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
        lambda: "gemini:gemma-4-31b-it",
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
        lambda raw_text: {
            "owner_name": "WRONG, NAME",
            "phone": "(404) 555-1212",
        },
    )

    result = process_card_min("fake.png")

    assert result["fields"]["owner_name"] == "PARKS, Carl"
    assert result["fields"]["date_of_death"] == "2021-10-16"
    assert result["fields"]["phone"] == "(404) 555-1212"


def test_process_card_min_rejects_date_like_structured_fallback_for_owner_fields(monkeypatch):
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
        lambda: "gemini:gemma-4-31b-it",
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
            "raw_text": "ADAMS, James\nOwner\nDate of burial\n3-20-41",
            "words": [],
            "card_confidence": 0.92,
        },
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.parse_structured_fields_with_gemini",
        lambda raw_text: {
            "owner_address": "3-20-41",
            "care_of": "3-20-41",
            "type_of_grave": "Description: Lot #64",
        },
    )

    result = process_card_min("fake.png")

    assert result["fields"]["owner_address"] is None
    assert result["fields"]["care_of"] is None
    assert result["fields"]["type_of_grave"] is None


def test_process_card_min_does_not_take_dates_from_structured_fallback(monkeypatch):
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
        lambda: "gemini:gemma-4-31b-it",
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
            "raw_text": "AARON, Benjamin L.\nDecember 14, 2004\nDecember 14, 2004\ndob 12/27/1966",
            "words": [],
            "card_confidence": 0.92,
        },
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.parse_structured_fields_with_gemini",
        lambda raw_text: {
            "date_of_death": "December 14, 2004",
            "date_of_burial": "December 14, 2004",
        },
    )

    result = process_card_min("fake.png")

    assert result["fields"]["date_of_death"] is None
    assert result["fields"]["date_of_burial"] is None


def test_process_card_min_caps_confidence_for_text_only_parsed_fields(monkeypatch):
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
        lambda: "gemini:gemma-4-31b-it",
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
            "raw_text": "ADAMS, James\nBoard of Health No.\nCox\nUndertaker\nGrave Fee\nSex\nM",
            "words": [],
            "card_confidence": 1.0,
        },
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.parse_structured_fields_with_gemini",
        lambda raw_text: {},
    )

    result = process_card_min("fake.png")

    assert result["fields"]["undertaker"] == "Cox"
    assert result["field_confidence"]["undertaker"] < 1.0
    assert result["card_confidence"] < 1.0


def test_process_card_min_scores_populated_core_fields_without_zeroing_for_missing_noise(monkeypatch):
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
        lambda: "gemini:gemma-4-31b-it",
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
            "raw_text": (
                "AARON, Benjamin L.\n"
                "Date of death December 8, 2004\n"
                "Date of burial December 14, 2004\n"
                "Description LOT# 316 Range B Grave# 2 Section 4 Block 5 Northside\n"
                "Sex M Age 38 Type of Grave SVC Vault\n"
                "Undertaker Haugabrooks\n"
            ),
            "words": [],
            "card_confidence": 0.80,
        },
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.parse_structured_fields_with_gemini",
        lambda raw_text: {},
    )

    result = process_card_min("fake.png")

    assert result["fields"]["owner_name"] == "AARON, Benjamin L."
    assert result["fields"]["svc_no"] is None
    assert result["card_confidence"] > 0.68


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
        lambda: "gemini:gemma-4-31b-it",
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
            return {
                "raw_text": "garbled text",
                "words": [],
                "card_confidence": 0.25,
            }
        return {
            "raw_text": "ADAMS, James\nDate of burial 3-20-41",
            "words": [],
            "card_confidence": 0.88,
        }

    monkeypatch.setattr(
        "southview.ocr.processor_min.run_ocr",
        fake_run_ocr,
    )

    def fake_fallback(raw_text):
        calls["fallback"] += 1
        return {"svc_no": "8047"}

    monkeypatch.setattr(
        "southview.ocr.processor_min.parse_structured_fields_with_gemini",
        fake_fallback,
    )

    result = process_card_min("fake.png")

    assert calls["ocr"] == 2
    assert calls["fallback"] == 1
    assert result["orientation"] == 270
    assert result["fields"]["svc_no"] == "8047"


def test_rotation_candidates_default_to_sideways_for_gemini(monkeypatch):
    monkeypatch.setattr(
        "southview.ocr.processor_min.get_ocr_engine_name",
        lambda: "gemini",
    )
    monkeypatch.setattr(
        "southview.ocr.processor_min.get_config",
        lambda: {"ocr": {"gemini": {"rotation_mode": "sideways"}}},
    )

    assert [degree for degree, _ in _rotation_candidates()] == [90, 270]


def test_orientation_score_uses_card_confidence_and_parsed_fields_when_words_missing():
    parsed = {
        "owner_name": {"value": "AARON, Benjamin L.", "support": []},
        "date_of_death": {"value": "2004-12-08", "support": []},
        "date_of_burial": {"value": "2004-12-14", "support": []},
        "svc_no": {"value": "49,711", "support": []},
    }

    better = _orientation_score(
        parsed,
        [],
        "AARON, Benjamin L.\nDate of death: December 8, 2004\nDate of burial: December 14, 2004\nSVC No: 49,711",
        {"card_confidence": 0.82},
    )
    worse = _orientation_score(
        {"owner_name": {"value": None, "support": []}},
        [],
        "garbled text",
        {"card_confidence": 0.3},
    )

    assert better > worse


def test_template_order_score_prefers_upright_record_order():
    upright = """AARON, Benjamin L.
Date of death December 8, 2004
Date of burial December 14, 2004
Description LOT# 316 Range B Grave# 2
Sex M
Age 38
Undertaker Haugabrooks
SVC No 49,711
"""

    reversed_order = """SVC No 49,711
Undertaker Haugabrooks
Age 38
Sex M
Description LOT# 316 Range B Grave# 2
Date of burial December 14, 2004
Date of death December 8, 2004
AARON, Benjamin L.
"""

    assert _template_order_score(upright) > _template_order_score(reversed_order)
