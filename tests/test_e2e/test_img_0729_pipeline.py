"""End-to-end regression test for IMG_0729.MOV processing."""

from __future__ import annotations

import copy
import os
from pathlib import Path

import pytest
from sqlalchemy import select

from southview.config import load_config, load_dotenv
from southview.db.engine import get_session
from southview.db.models import Card, OCRResult, Video
from southview.ingest.video_upload import compute_file_hash, upload_video
from southview.jobs.manager import create_job
from southview.jobs.runner import run_full_pipeline

FIXTURE_VIDEO_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "videos" / "IMG_0729.MOV"
)
FIXTURE_VIDEO_SHA256 = "5bceba17f8e23152742b070c0eeb8b19d70c69c11150075eed72d37f9ed98298"

EXPECTED_TABLE_ROWS = [
    (
        1,
        152,
        "ADAMS, James",
        None,
        None,
        None,
        None,
        None,
        "1941-03-20",
        "Lot #64- Range G- Grave 9- Section 2- Block 2 SS",
        "M",
        "54",
        None,
        None,
        "Cox",
        None,
        "8047",
        "pending",
    ),
    (
        2,
        256,
        "AARON, Benjamin L.",
        "5566 Marbut Road Lithonia, GA.",
        "ESTATE c/o Mrs. Helen Reaves",
        "Mother",
        "(404) 784-2878",
        "2004-12-08",
        "2004-12-14",
        "LOT# 316 Range B Grave# 2 Section 4 Block 5 Northside",
        "M",
        "38",
        "SVC Vault",
        "$675.00",
        "Haugabrooks",
        None,
        "49,711",
        "pending",
    ),
    (
        3,
        328,
        "ADAMS, James",
        None,
        None,
        None,
        None,
        None,
        "1941-03-20",
        "Lot #64- Range G- Grave 9- Section 2- Block 2 SS",
        "M",
        "54",
        None,
        None,
        "Cox",
        None,
        "8047",
        "pending",
    ),
    (
        4,
        388,
        "AARON, Benjamin L.",
        "5566 Marbut Road Lithonia, GA.",
        "Mrs. Helen Reaves",
        "Mother",
        "(404) 784-2878",
        "2004-12-08",
        "2004-12-14",
        "LOT# 316 Range B Grave# 2 Section 4 Block 5 Northside",
        "M",
        "38",
        "SVC Vault",
        "$675.00",
        "Haugabrooks",
        None,
        "49,711",
        "pending",
    ),
    (
        5,
        460,
        "ADAMS, James",
        None,
        None,
        None,
        None,
        None,
        "1941-03-20",
        "Lot #64- Range G- Grave 9- Section 2- Block 2 SS",
        "M",
        "54",
        None,
        None,
        "Cox",
        None,
        "8047",
        "pending",
    ),
]


@pytest.fixture
def e2e_config(monkeypatch, tmp_path, tmp_db):
    """Patch config lookups so e2e work uses a temp DB and temp storage."""
    config = copy.deepcopy(load_config())
    config["database"]["path"] = str(tmp_db)
    config["storage"]["videos_dir"] = str(tmp_path / "videos")
    config["storage"]["frames_dir"] = str(tmp_path / "frames")
    config["storage"]["backups_dir"] = str(tmp_path / "backups")
    config["storage"]["exports_dir"] = str(tmp_path / "exports")

    def _get_config(*_args, **_kwargs):
        return config

    for target in (
        "southview.config.get_config",
        "southview.ingest.video_upload.get_config",
        "southview.jobs.runner.get_config",
        "southview.jobs.cleanup.get_config",
        "southview.extraction.frame_extractor.get_config",
        "southview.extraction.scene_detect.get_config",
        "southview.ocr.batch.get_config",
        "southview.ocr.engine.get_config",
        "southview.ocr.gemini_wrapper.get_config",
        "southview.ocr.tesseract_wrapper.get_config",
        "southview.ocr.preprocess.get_config",
        "southview.ocr.processor_min.get_config",
    ):
        monkeypatch.setattr(target, _get_config)

    return config


def _gemini_key_available(config: dict) -> bool:
    env_name = str(
        config.get("ocr", {}).get("gemini", {}).get("api_key_env", "GEMINI_API_KEY")
    ).strip() or "GEMINI_API_KEY"
    if os.getenv(env_name):
        return True
    return env_name == "GEMINI_API_KEY" and bool(os.getenv("GOOGLE_API_KEY"))


def test_img_0729_pipeline_writes_expected_rows(e2e_config):
    """Regression: this video should produce the same 5 known OCR rows."""
    # Respect local .env so GEMINI_API_KEY doesn't have to be shell-exported.
    load_dotenv(override=False)

    if not FIXTURE_VIDEO_PATH.exists():
        pytest.fail(f"Missing e2e fixture video: {FIXTURE_VIDEO_PATH}")
    assert compute_file_hash(FIXTURE_VIDEO_PATH) == FIXTURE_VIDEO_SHA256
    if not _gemini_key_available(e2e_config):
        pytest.skip(
            "This e2e test requires a Gemini API key in GEMINI_API_KEY "
            "(or GOOGLE_API_KEY when api_key_env is GEMINI_API_KEY)."
        )

    uploaded_video = upload_video(FIXTURE_VIDEO_PATH)
    job = create_job(uploaded_video.id, "full_pipeline")
    run_full_pipeline(job.id, uploaded_video.id)

    session = get_session()
    try:
        video = session.query(Video).get(uploaded_video.id)
        assert video is not None
        assert video.status == "completed"

        rows = session.execute(
            select(
                Card.sequence_index,
                Card.frame_number,
                OCRResult.deceased_name,
                OCRResult.address,
                OCRResult.owner,
                OCRResult.relation,
                OCRResult.phone,
                OCRResult.date_of_death,
                OCRResult.date_of_burial,
                OCRResult.description,
                OCRResult.sex,
                OCRResult.age,
                OCRResult.grave_type,
                OCRResult.grave_fee,
                OCRResult.undertaker,
                OCRResult.board_of_health_no,
                OCRResult.svc_no,
                OCRResult.review_status,
            )
            .join(OCRResult, OCRResult.card_id == Card.id)
            .where(Card.video_id == uploaded_video.id)
            .order_by(Card.sequence_index.asc())
        ).all()
    finally:
        session.close()

    assert rows == EXPECTED_TABLE_ROWS
