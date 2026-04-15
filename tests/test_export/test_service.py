"""Tests for ZIP export of approved card images."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from southview.api.routes.export import export_video_approved
from southview.db.engine import get_session
from southview.db.models import Card, OCRResult, Video
from southview.export.service import ExportIncompleteError, export_approved_cards_zip


def _seed_export_card(*, image_path: str) -> str:
    session = get_session()
    try:
        video = Video(
            filename="export.mp4",
            filepath="/tmp/export.mp4",
            file_hash=f"hash-{image_path}",
            status="completed",
        )
        session.add(video)
        session.flush()

        card = Card(
            video_id=video.id,
            frame_number=10,
            image_path=image_path,
            sequence_index=1,
        )
        session.add(card)
        session.flush()

        ocr = OCRResult(
            card_id=card.id,
            raw_text="Sample raw text",
            confidence_score=0.8,
            review_status="approved",
            deceased_name="SMITH, John",
            date_of_death="2021-10-30",
        )
        session.add(ocr)
        session.commit()
        return video.id
    finally:
        session.close()


def test_export_approved_cards_zip_raises_when_any_source_image_is_missing(tmp_db, tmp_path):
    missing_image = tmp_path / "missing-card.jpg"
    video_id = _seed_export_card(image_path=str(missing_image))
    config = {"storage": {"exports_dir": str(tmp_path / "exports")}}

    with patch("southview.export.service.get_config", return_value=config):
        with pytest.raises(ExportIncompleteError, match="source image\\(s\\) are missing"):
            export_approved_cards_zip(video_id)

    assert not (Path(config["storage"]["exports_dir"]) / "videos" / video_id).exists()


def test_export_video_route_returns_conflict_for_incomplete_export():
    with patch(
        "southview.api.routes.export.export_approved_cards_zip",
        side_effect=ExportIncompleteError("Cannot export because source image is missing."),
    ):
        with pytest.raises(HTTPException) as exc_info:
            export_video_approved("video-123")

    assert exc_info.value.status_code == 409
    assert "source image is missing" in exc_info.value.detail
