"""Tests for hysteresis-based frame extraction."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from southview.extraction import frame_extractor


def _load_decisions(decisions_path: Path) -> list[dict]:
    lines = decisions_path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _base_config(tmp_path: Path, **frame_overrides) -> dict:
    frame_config = {
        "analysis_width": 320,
        "roi_margin_x": 0.20,
        "roi_margin_top": 0.15,
        "roi_margin_bottom": 0.20,
        "enter_motion_threshold": 12.0,
        "enter_motion_consecutive_frames": 2,
        "exit_motion_threshold": 6.0,
        "exit_motion_consecutive_frames": 5,
        "min_emit_stable_frames": 10,
        "low_confidence_stable_frames": 12,
        "low_motion_candidate_threshold": 6.0,
        "fallback_motion_weight": 4.0,
        "missed_insert_check_start_frames": 18,
        "missed_insert_check_interval_frames": 6,
        "missed_insert_cell_threshold": 8.0,
        "missed_insert_required_cells": 2,
        "missed_insert_required_checks": 2,
        "missed_insert_seed_recent_frames": 6,
        "blur_threshold": 50.0,
        "dedup_enabled": True,
        "dedup_hamming_threshold": 6,
        "dhash_size": 8,
    }
    frame_config.update(frame_overrides)
    return {
        "storage": {"frames_dir": str(tmp_path / "frames_root")},
        "frame_extraction": frame_config,
    }


def _write_video(video_path: Path, frames: list[np.ndarray], *, fps: float = 30.0) -> None:
    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    for frame in frames:
        writer.write(frame)
    writer.release()


def _run_extraction(
    tmp_path: Path,
    frames: list[np.ndarray],
    *,
    video_id: str = "vid-test",
    **frame_overrides,
) -> tuple[list[dict], Path]:
    video_path = tmp_path / "synthetic.mp4"
    output_dir = tmp_path / "frames"
    _write_video(video_path, frames)
    config = _base_config(tmp_path, **frame_overrides)
    with patch.object(frame_extractor, "get_config", return_value=config):
        results = frame_extractor.extract_frames(video_path, video_id, output_dir=output_dir)
    return results, output_dir


def _make_card(kind: int, *, width: int = 640, height: int = 480, brightness: float = 1.0) -> np.ndarray:
    frame = np.full((height, width, 3), 255, dtype=np.uint8)
    cv2.rectangle(frame, (70, 50), (width - 70, height - 80), (240, 240, 240), -1)
    cv2.rectangle(frame, (70, 50), (width - 70, height - 80), (32, 32, 32), 4)

    if kind == 0:
        for y in range(90, height - 120, 28):
            cv2.line(frame, (110, y), (width - 110, y), (0, 0, 0), 3)
        cv2.rectangle(frame, (130, 140), (260, 260), (0, 0, 0), -1)
    elif kind == 1:
        for x in range(120, width - 120, 28):
            cv2.line(frame, (x, 90), (x, height - 120), (0, 0, 0), 3)
        cv2.circle(frame, (width // 2, 200), 80, (0, 0, 0), -1)
    elif kind == 2:
        for offset in range(-height, height, 30):
            cv2.line(
                frame,
                (0, max(0, offset)),
                (width, min(height, offset + width)),
                (0, 0, 0),
                3,
            )
        cv2.putText(
            frame,
            "2",
            (width // 2 - 40, height // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            5,
            (255, 255, 255),
            10,
            cv2.LINE_AA,
        )
    elif kind == 3:
        for offset in range(0, width + height, 30):
            cv2.line(
                frame,
                (max(0, offset - height), min(height, offset)),
                (min(width, offset), max(0, offset - width)),
                (0, 0, 0),
                3,
            )
        cv2.rectangle(frame, (width // 2 - 100, height // 2 - 90), (width // 2 + 100, height // 2 + 90), (255, 255, 255), -1)
        cv2.rectangle(frame, (width // 2 - 60, height // 2 - 50), (width // 2 + 60, height // 2 + 50), (0, 0, 0), -1)
    else:
        raise ValueError(f"Unknown card kind: {kind}")

    if brightness != 1.0:
        frame = np.clip(frame.astype(np.float32) * brightness, 0, 255).astype(np.uint8)
    return frame


def _blend(frame_a: np.ndarray, frame_b: np.ndarray, alpha: float) -> np.ndarray:
    return cv2.addWeighted(frame_a, 1.0 - alpha, frame_b, alpha, 0.0)


def _shift(frame: np.ndarray, dx: int, dy: int) -> np.ndarray:
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(
        frame,
        matrix,
        (frame.shape[1], frame.shape[0]),
        borderMode=cv2.BORDER_REPLICATE,
    )


def _make_white_card(
    *,
    width: int = 640,
    height: int = 480,
    text_shift: int = 0,
    top_shadow: int = 0,
    bottom_marker: int = 0,
    center_stamp: int = 0,
) -> np.ndarray:
    frame = np.full((height, width, 3), 245, dtype=np.uint8)
    cv2.rectangle(frame, (80, 60), (width - 80, height - 80), (252, 252, 252), -1)
    cv2.rectangle(frame, (80, 60), (width - 80, height - 80), (220, 220, 220), 4)

    if top_shadow > 0:
        cv2.rectangle(
            frame,
            (80, 60),
            (width - 80, 60 + top_shadow),
            (208, 208, 208),
            -1,
        )

    if bottom_marker > 0:
        cv2.rectangle(
            frame,
            (width - 220, height - 180),
            (width - 220 + bottom_marker, height - 120),
            (100, 100, 100),
            -1,
        )

    if center_stamp > 0:
        cv2.circle(
            frame,
            (width // 2 + 90, height // 2 + 40),
            center_stamp,
            (110, 110, 110),
            -1,
        )

    for y in range(118, height - 128, 38):
        cv2.line(frame, (126, y), (width - 126, y), (92, 92, 92), 2)

    cv2.putText(
        frame,
        "CARD",
        (148 + text_shift, 220),
        cv2.FONT_HERSHEY_SIMPLEX,
        2.0,
        (52, 52, 52),
        4,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        "LOT",
        (188, 308),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.6,
        (76, 76, 76),
        3,
        cv2.LINE_AA,
    )
    return frame


class TestFrameExtractor:
    def test_overlapping_four_card_video_yields_four_captures_outside_overlap_frames(self, tmp_path):
        cards = [_make_card(i) for i in range(4)]
        frames = [np.zeros_like(cards[0]) for _ in range(4)]
        frames += [_blend(np.zeros_like(cards[0]), cards[0], alpha) for alpha in (0.2, 0.45, 0.7, 0.9)]
        for idx, card in enumerate(cards):
            frames += [card.copy() for _ in range(14)]
            if idx < len(cards) - 1:
                nxt = cards[idx + 1]
                frames += [_blend(card, nxt, alpha) for alpha in (0.2, 0.4, 0.6, 0.8)]

        results, output_dir = _run_extraction(tmp_path, frames)

        assert len(results) == 4
        assert [item["sequence_index"] for item in results] == [1, 2, 3, 4]
        assert 8 <= results[0]["frame_number"] <= 21
        assert 26 <= results[1]["frame_number"] <= 39
        assert 44 <= results[2]["frame_number"] <= 57
        assert 62 <= results[3]["frame_number"] <= 75
        assert [item["extraction_confidence"] for item in results[:3]] == ["high", "high", "high"]
        assert results[3]["needs_review"] is True

        decisions = _load_decisions(output_dir / "extraction_decisions.jsonl")
        accepted = [row for row in decisions if row["decision"] == "accepted"]
        assert len(accepted) == 4
        for row in accepted:
            assert row["selected_motion_score"] <= 6.0

        manifest = json.loads((output_dir / "extraction_manifest.json").read_text(encoding="utf-8"))
        assert manifest["counts"]["accepted"] == 4
        assert len(manifest["accepted_frames"]) == 4

    def test_jostle_only_clip_rejects_second_duplicate_capture(self, tmp_path):
        base = _make_card(0)
        frames = [np.zeros_like(base) for _ in range(4)]
        frames += [_blend(np.zeros_like(base), base, alpha) for alpha in (0.2, 0.45, 0.7, 0.9)]
        frames += [base.copy() for _ in range(14)]
        frames += [_shift(base, dx, dy) for dx, dy in ((18, 10), (-18, -10))]
        frames += [base.copy() for _ in range(14)]

        results, output_dir = _run_extraction(tmp_path, frames)

        assert len(results) == 1
        decisions = _load_decisions(output_dir / "extraction_decisions.jsonl")
        deduped = [row for row in decisions if row["decision"] == "rejected_dedup"]
        assert len(deduped) == 1
        assert deduped[0]["duplicate_of_frame_number"] == results[0]["frame_number"]
        assert deduped[0]["duplicate_distance"] < 6

    def test_stable_backstop_splits_silent_white_on_white_insert(self, tmp_path):
        first = _make_white_card()
        transition_frames = [
            _make_white_card(
                text_shift=round(4 * step / 6),
                top_shadow=round(12 * step / 6),
                bottom_marker=round(36 * step / 6),
                center_stamp=round(24 * step / 6),
            )
            for step in range(1, 7)
        ]
        second = transition_frames[-1]

        frames = [np.zeros_like(first) for _ in range(4)]
        frames += [_blend(np.zeros_like(first), first, alpha) for alpha in (0.2, 0.45, 0.7, 0.9)]
        frames += [first.copy() for _ in range(18)]
        frames += transition_frames
        frames += [second.copy() for _ in range(18)]

        results, output_dir = _run_extraction(
            tmp_path,
            frames,
            missed_insert_check_start_frames=12,
            missed_insert_check_interval_frames=3,
            missed_insert_cell_threshold=5.0,
            missed_insert_required_cells=2,
            missed_insert_required_checks=2,
            missed_insert_seed_recent_frames=3,
        )

        assert len(results) == 2
        assert results[1]["frame_number"] > results[0]["frame_number"]

        decisions = _load_decisions(output_dir / "extraction_decisions.jsonl")
        accepted = [row for row in decisions if row["decision"] == "accepted"]
        assert len(accepted) == 2

    def test_stable_backstop_ignores_mild_lighting_flicker(self, tmp_path):
        base = _make_card(1)
        frames = [np.zeros_like(base) for _ in range(4)]
        frames += [_blend(np.zeros_like(base), base, alpha) for alpha in (0.2, 0.45, 0.7, 0.9)]
        frames += [base.copy() for _ in range(18)]
        frames += [
            _make_card(1, brightness=brightness)
            for brightness in (
                1.00,
                1.008,
                0.996,
                1.010,
                1.004,
                1.00,
                1.006,
                0.994,
                1.002,
                1.005,
                1.000,
                0.997,
            )
        ]

        results, output_dir = _run_extraction(
            tmp_path,
            frames,
            missed_insert_check_start_frames=12,
            missed_insert_check_interval_frames=3,
            missed_insert_cell_threshold=5.0,
            missed_insert_required_cells=2,
            missed_insert_required_checks=2,
            missed_insert_seed_recent_frames=3,
        )

        assert len(results) == 1
        decisions = _load_decisions(output_dir / "extraction_decisions.jsonl")
        assert [row["decision"] for row in decisions] == ["accepted"]

    def test_rapid_next_card_insertion_is_not_missed_without_cooldown(self, tmp_path):
        first = _make_card(0)
        second = _make_card(1)
        frames = [np.zeros_like(first) for _ in range(4)]
        frames += [_blend(np.zeros_like(first), first, alpha) for alpha in (0.2, 0.45, 0.7, 0.9)]
        frames += [first.copy() for _ in range(14)]
        frames += [_blend(first, second, alpha) for alpha in (0.2, 0.4, 0.6, 0.8)]
        frames += [second.copy() for _ in range(14)]

        results, _ = _run_extraction(tmp_path, frames)

        assert len(results) == 2
        assert 8 <= results[0]["frame_number"] <= 21
        assert 26 <= results[1]["frame_number"] <= 39

    def test_long_final_stable_card_emits_once_at_eof(self, tmp_path):
        base = _make_card(2)
        frames = [np.zeros_like(base) for _ in range(4)]
        frames += [_blend(np.zeros_like(base), base, alpha) for alpha in (0.2, 0.45, 0.7, 0.9)]
        frames += [base.copy() for _ in range(18)]

        results, output_dir = _run_extraction(tmp_path, frames)

        assert len(results) == 1
        assert results[0]["needs_review"] is True
        assert results[0]["extraction_confidence"] == "low"
        assert results[0]["stable_duration_frames"] >= 10

        decisions = _load_decisions(output_dir / "extraction_decisions.jsonl")
        assert [row["decision"] for row in decisions] == ["accepted"]

    def test_short_but_emittable_stable_window_is_marked_needs_review(self, tmp_path):
        first = _make_card(0)
        second = _make_card(1)
        third = _make_card(2)
        frames = [np.zeros_like(first) for _ in range(4)]
        frames += [_blend(np.zeros_like(first), first, alpha) for alpha in (0.2, 0.45, 0.7, 0.9)]
        frames += [first.copy() for _ in range(11)]
        frames += [_blend(first, second, alpha) for alpha in (0.2, 0.4, 0.6, 0.8)]
        frames += [second.copy() for _ in range(14)]
        frames += [_blend(second, third, alpha) for alpha in (0.2, 0.4, 0.6, 0.8)]
        frames += [third.copy() for _ in range(14)]

        results, _ = _run_extraction(tmp_path, frames)

        assert len(results) == 3
        assert results[0]["needs_review"] is True
        assert results[0]["extraction_confidence"] == "low"
        assert results[0]["stable_duration_frames"] < 12
        assert results[1]["needs_review"] is False

    def test_blur_rejection_writes_metadata_to_manifest_and_jsonl(self, tmp_path):
        sharp = _make_card(0)
        blurred = cv2.GaussianBlur(sharp, (41, 41), 10.0)
        frames = [np.zeros_like(blurred) for _ in range(4)]
        frames += [_blend(np.zeros_like(blurred), blurred, alpha) for alpha in (0.2, 0.45, 0.7, 0.9)]
        frames += [blurred.copy() for _ in range(14)]

        results, output_dir = _run_extraction(tmp_path, frames, blur_threshold=2000.0)

        assert results == []
        decisions = _load_decisions(output_dir / "extraction_decisions.jsonl")
        assert [row["decision"] for row in decisions] == ["rejected_blur"]
        rejected = decisions[0]
        assert rejected["selected_sharpness"] < 2000.0
        assert rejected["stable_duration_frames"] >= 10
        assert Path(rejected["image_path"]).exists()

        manifest = json.loads((output_dir / "extraction_manifest.json").read_text(encoding="utf-8"))
        assert manifest["counts"]["accepted"] == 0
        assert manifest["counts"]["rejected_blur"] == 1
        assert manifest["accepted_frames"] == []

    def test_failed_extraction_preserves_previous_results(self, tmp_path):
        output_dir = tmp_path / "frames"
        output_dir.mkdir(parents=True, exist_ok=True)
        previous_decisions = '{"decision":"accepted","image_path":"old-card.jpg"}\n'
        previous_manifest = '{"counts":{"accepted":1}}'
        old_frame = output_dir / "card_0001.jpg"
        (output_dir / "extraction_decisions.jsonl").write_text(previous_decisions, encoding="utf-8")
        (output_dir / "extraction_manifest.json").write_text(previous_manifest, encoding="utf-8")
        old_frame.write_bytes(b"old-frame")

        config = _base_config(tmp_path)
        with patch.object(frame_extractor, "get_config", return_value=config), \
             patch("cv2.VideoCapture", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError, match="boom"):
                frame_extractor.extract_frames(
                    video_path=tmp_path / "broken.mp4",
                    video_id="vid-preserve",
                    output_dir=output_dir,
                )

        assert (output_dir / "extraction_decisions.jsonl").read_text(encoding="utf-8") == previous_decisions
        assert (output_dir / "extraction_manifest.json").read_text(encoding="utf-8") == previous_manifest
        assert old_frame.read_bytes() == b"old-frame"
        assert not list(tmp_path.glob(".frames.extracting-*"))
