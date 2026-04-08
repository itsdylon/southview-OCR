import csv
import json

from PIL import Image

from southview import __main__ as cli
from southview.ocr.bakeoff import runner as bakeoff_runner
from southview.ocr.bakeoff.artifacts import ADJUDICATION_FILENAME, PREDICTIONS_FILENAME
from southview.ocr.bakeoff.types import ProviderResult


def _write_png(path):
    image = Image.new("RGB", (12, 12), (255, 255, 255))
    image.save(path)


def _write_manifest(path, image_path):
    with path.open("w", newline="", encoding="utf-8") as f:
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
        writer.writerow(["card-001", str(image_path), "hard", "SMITH, John", "2021-10-30"])


def test_bakeoff_cli_run_and_summarize_with_mocked_router(tmp_path, monkeypatch):
    image_path = tmp_path / "card.png"
    manifest_path = tmp_path / "manifest.csv"
    run_dir = tmp_path / "run"

    _write_png(image_path)
    _write_manifest(manifest_path, image_path)

    class _FakeRouter:
        def run_model(self, model_id, image_path):
            if model_id == "gpt-4o":
                return ProviderResult(
                    deceased_name="SMITH, John",
                    date_of_death="2021-10-30",
                    raw_text='{"deceased_name":"SMITH, John","date_of_death":"2021-10-30"}',
                    latency_ms=10.0,
                )
            return ProviderResult(
                deceased_name="SMYTH, John",
                date_of_death="",
                raw_text='{"deceased_name":"SMYTH, John","date_of_death":""}',
                latency_ms=20.0,
            )

    monkeypatch.setattr(bakeoff_runner, "ModelRouter", lambda: _FakeRouter())

    cli._run_bakeoff_command(
        [
            "run",
            "--manifest",
            str(manifest_path),
            "--out-dir",
            str(run_dir),
        ]
    )

    predictions_path = run_dir / PREDICTIONS_FILENAME
    adjudication_path = run_dir / ADJUDICATION_FILENAME
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"

    assert predictions_path.exists()
    assert adjudication_path.exists()
    assert summary_json.exists()
    assert summary_md.exists()

    with predictions_path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3
    assert [r["model_id"] for r in rows] == ["gpt-4.1-mini", "gemini-2.0-flash", "gpt-4o"]

    # Apply one adjudication correction and re-summarize.
    with adjudication_path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2  # gpt-4o is exact, others mismatch

    rows[0]["human_name_correct"] = "true"
    rows[0]["human_dod_correct"] = "true"
    rows[0]["adjudication_notes"] = "Human accepted this prediction."

    with adjudication_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    cli._run_bakeoff_command(
        [
            "summarize",
            "--run-dir",
            str(run_dir),
            "--adjudication",
            str(adjudication_path),
        ]
    )

    data = json.loads(summary_json.read_text(encoding="utf-8"))
    assert data["adjudication_applied"] is True
    assert data["ranking"][0]["model_id"] in {"gpt-4.1-mini", "gpt-4o"}
