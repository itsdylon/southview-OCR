"""Idempotency cleanup — remove previous results before reprocessing."""

import shutil
from pathlib import Path

from southview.config import get_config
from southview.db.engine import get_session
from southview.db.models import Card, OCRResult


def cleanup_previous_results(video_id: str, *, remove_frames: bool = True) -> None:
    """Delete all cards and OCR results for a video to allow clean reprocessing."""
    session = get_session()
    try:
        cards = session.query(Card).filter_by(video_id=video_id).all()

        for card in cards:
            # Delete OCR result
            ocr = session.query(OCRResult).filter_by(card_id=card.id).first()
            if ocr:
                session.delete(ocr)
            session.delete(card)

        session.commit()

        # Remove frame images
        if remove_frames:
            config = get_config()
            frames_dir = Path(config["storage"]["frames_dir"]) / video_id
            if frames_dir.exists():
                shutil.rmtree(frames_dir)

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
