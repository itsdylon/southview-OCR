"""Tests for confidence scoring."""

from southview.ocr.confidence import compute_card_confidence, extract_word_confidences


def test_compute_card_confidence_normal():
    words = [
        {"text": "hello", "confidence": 90, "bbox": [0, 0, 10, 10]},
        {"text": "world", "confidence": 80, "bbox": [10, 0, 10, 10]},
    ]
    score = compute_card_confidence(words)
    assert score == 0.85


def test_compute_card_confidence_empty():
    assert compute_card_confidence([]) == 0.0


def test_extract_word_confidences():
    tesseract_data = [
        {
            "text": "test",
            "conf": 95,
            "left": 0,
            "top": 0,
            "width": 50,
            "height": 20,
            "block_num": 1,
            "par_num": 1,
            "line_num": 1,
            "word_num": 1,
        }
    ]
    result = extract_word_confidences(tesseract_data)
    assert len(result) == 1
    assert result[0]["text"] == "test"
    assert result[0]["confidence"] == 95
    assert result[0]["bbox"] == [0, 0, 50, 20]
