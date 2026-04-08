import csv

import pytest
from PIL import Image

from southview.ocr.bakeoff.dataset import load_manifest


def _write_png(path):
    image = Image.new("RGB", (16, 16), (255, 255, 255))
    image.save(path)


def test_load_manifest_valid(tmp_path):
    image_path = tmp_path / "card1.png"
    _write_png(image_path)

    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "card_id",
                "image_path",
                "difficulty_bucket",
                "deceased_name",
                "date_of_death",
            ]
        )
        writer.writerow(["c1", str(image_path), "hard", "Smith, John", "10/30/2021"])

    rows = load_manifest(manifest)

    assert len(rows) == 1
    assert rows[0].card_id == "c1"
    assert rows[0].difficulty_bucket == "hard"
    assert rows[0].date_of_death == "2021-10-30"


def test_load_manifest_missing_required_column(tmp_path):
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["card_id", "image_path", "difficulty_bucket", "deceased_name"])
        writer.writerow(["c1", "card.png", "hard", "Smith, John"])

    with pytest.raises(ValueError, match="missing required columns"):
        load_manifest(manifest)


def test_load_manifest_invalid_date(tmp_path):
    image_path = tmp_path / "card1.png"
    _write_png(image_path)

    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "card_id",
                "image_path",
                "difficulty_bucket",
                "deceased_name",
                "date_of_death",
            ]
        )
        writer.writerow(["c1", str(image_path), "hard", "Smith, John", "2021-30-10"])

    with pytest.raises(ValueError, match="invalid date_of_death"):
        load_manifest(manifest)
