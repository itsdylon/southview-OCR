"""Tests for frame extraction blur filtering and deduplication."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from southview.extraction import frame_extractor
from southview.extraction.phash import compute_phash, hamming_distance


def _sharp_pattern(width: int = 320, height: int = 240) -> np.ndarray:
    """Generate a high-frequency checkerboard-like frame."""
    y, x = np.indices((height, width))
    grid = ((x // 8 + y // 8) % 2) * 255
    frame = np.stack([grid, grid, grid], axis=-1).astype(np.uint8)
    return frame


def _blurred_from(frame: np.ndarray) -> np.ndarray:
    return cv2.GaussianBlur(frame, (11, 11), 3.0)


def _distinct_pattern(width: int = 320, height: int = 240) -> np.ndarray:
    """Generate a frame that is perceptually unlike _sharp_pattern."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.circle(frame, center=(width // 2, height // 2), radius=70, color=(255, 255, 255), thickness=-1)
    return frame


def _load_decisions(decisions_path: Path) -> list[dict]:
    lines = decisions_path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


class TestFrameExtractor:
    def test_blur_rejection_writes_jsonl_and_manifest(self, tiny_mp4, tmp_path):
        output_dir = tmp_path / "frames"
        video_id = "vid-blur"
        blur = np.zeros((240, 320, 3), dtype=np.uint8)
        sharp = _sharp_pattern()

        config = {
            "storage": {"frames_dir": str(tmp_path / "frames_root")},
            "frame_extraction": {
                "min_stable_frames": 1,
                "blur_threshold": 50.0,
                "dedup_enabled": True,
                "dedup_hamming_threshold": 8,
            },
        }

        with patch.object(frame_extractor, "get_config", return_value=config), \
             patch.object(frame_extractor, "detect_transitions", return_value=[3, 6]), \
             patch.object(
                 frame_extractor,
                 "_find_best_frame",
                 side_effect=[(blur, 1), (sharp, 4), (blur, 8)],
             ), \
             patch.object(
                 frame_extractor,
                 "_append_decision",
                 wraps=frame_extractor._append_decision,
             ) as append_spy:
            results = frame_extractor.extract_frames(
                video_path=tiny_mp4,
                video_id=video_id,
                output_dir=output_dir,
            )

        assert len(results) == 1
        assert results[0]["frame_number"] == 4
        assert results[0]["sequence_index"] == 1
        assert Path(results[0]["image_path"]).exists()

        decisions_path = output_dir / "extraction_decisions.jsonl"
        manifest_path = output_dir / "extraction_manifest.json"
        assert decisions_path.exists()
        assert manifest_path.exists()

        decisions = _load_decisions(decisions_path)
        kinds = [d["decision"] for d in decisions]
        assert kinds.count("accepted") == 1
        assert kinds.count("rejected_blur") == 2
        assert kinds.count("rejected_dedup") == 0

        # One JSONL append per decision ensures incremental writes.
        assert append_spy.call_count == len(decisions)

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["counts"]["accepted"] == 1
        assert manifest["counts"]["rejected_blur"] == 2
        assert manifest["counts"]["rejected_dedup"] == 0
        assert manifest["files"]["decisions_jsonl"] == str(decisions_path)

    def test_dedup_keeps_sharpest_adjacent_candidate(self, tiny_mp4, tmp_path):
        output_dir = tmp_path / "frames"
        video_id = "vid-dedup"

        sharp = _sharp_pattern()
        softer = _blurred_from(sharp)
        distinct = _distinct_pattern()

        d12 = hamming_distance(compute_phash(sharp), compute_phash(softer))
        d23 = hamming_distance(compute_phash(softer), compute_phash(distinct))
        assert d23 > d12

        config = {
            "storage": {"frames_dir": str(tmp_path / "frames_root")},
            "frame_extraction": {
                "min_stable_frames": 1,
                "blur_threshold": 0.0,
                "dedup_enabled": True,
                "dedup_hamming_threshold": d12,
            },
        }

        with patch.object(frame_extractor, "get_config", return_value=config), \
             patch.object(frame_extractor, "detect_transitions", return_value=[3, 6]), \
             patch.object(
                 frame_extractor,
                 "_find_best_frame",
                 side_effect=[(sharp, 2), (softer, 5), (distinct, 8)],
             ):
            results = frame_extractor.extract_frames(
                video_path=tiny_mp4,
                video_id=video_id,
                output_dir=output_dir,
            )

        assert len(results) == 2
        assert [r["sequence_index"] for r in results] == [1, 2]
        assert [r["frame_number"] for r in results] == [2, 8]

        decisions = _load_decisions(output_dir / "extraction_decisions.jsonl")
        accepted_frames = [d["frame_number"] for d in decisions if d["decision"] == "accepted"]
        dedup_rejects = [d for d in decisions if d["decision"] == "rejected_dedup"]
        assert accepted_frames == [2, 8]
        assert len(dedup_rejects) == 1
        assert dedup_rejects[0]["frame_number"] == 5
        assert dedup_rejects[0]["duplicate_of_frame_number"] == 2

        manifest = json.loads((output_dir / "extraction_manifest.json").read_text(encoding="utf-8"))
        assert manifest["counts"]["accepted"] == 2
        assert manifest["counts"]["rejected_dedup"] == 1
        assert manifest["counts"]["rejected_blur"] == 0
