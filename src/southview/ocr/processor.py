"""Main OCR processing orchestrator."""

import json

import pytesseract

from southview.config import get_config
from southview.db.engine import get_session
from southview.db.models import Card, OCRResult
from southview.ocr.confidence import compute_card_confidence, extract_word_confidences
from southview.ocr.preprocess import preprocess_image
from southview.ocr.tesseract_wrapper import run_tesseract


def process_card(card: Card) -> OCRResult:
    """Run the full OCR pipeline on a single card image."""
    config = get_config()
    ocr_config = config["ocr"]
    thresholds = ocr_config["confidence"]

    # Pre-process
    processed_image = preprocess_image(card.image_path)

    # Run Tesseract
    tesseract_data = run_tesseract(processed_image)

    # Extract confidences
    word_confs = extract_word_confidences(tesseract_data)
    card_confidence = compute_card_confidence(word_confs)

    # Determine review status
    if card_confidence >= thresholds["auto_approve"]:
        review_status = "approved"
    elif card_confidence < thresholds["review_threshold"]:
        review_status = "flagged"
    else:
        review_status = "pending"

    # Build raw text from words
    raw_text = " ".join(w["text"] for w in word_confs if w["text"].strip())

    # Get Tesseract version
    try:
        version = pytesseract.get_tesseract_version().public
        engine_version = f"tesseract-{version}"
    except Exception:
        engine_version = "tesseract-unknown"

    # Store result
    session = get_session()
    try:
        ocr_result = OCRResult(
            card_id=card.id,
            raw_text=raw_text,
            confidence_score=card_confidence,
            word_confidences=json.dumps(word_confs),
            ocr_engine_version=engine_version,
            review_status=review_status,
        )
        session.add(ocr_result)
        session.commit()
        return ocr_result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
