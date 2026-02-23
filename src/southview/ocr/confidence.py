"""Confidence score computation."""


def extract_word_confidences(tesseract_data: list[dict]) -> list[dict]:
    """
    Extract word-level confidence data from Tesseract output.

    Returns list of dicts with: text, confidence (0–100), bbox [left, top, width, height].
    """
    return [
        {
            "text": word["text"],
            "confidence": word["conf"],
            "bbox": [word["left"], word["top"], word["width"], word["height"]],
        }
        for word in tesseract_data
    ]


def compute_card_confidence(word_confidences: list[dict]) -> float:
    """
    Compute card-level confidence from word confidences.

    Returns a score between 0.0 and 1.0 (mean of word confidences / 100).
    Returns 0.0 if no words were detected.
    """
    if not word_confidences:
        return 0.0

    total = sum(w["confidence"] for w in word_confidences)
    return total / (len(word_confidences) * 100)
