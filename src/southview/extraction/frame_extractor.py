"""Main frame extraction orchestrator."""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from southview.config import get_config
from southview.extraction.phash import compute_dhash, hamming_distance
from southview.extraction.sharpness import compute_sharpness

logger = logging.getLogger(__name__)

_JPEG_WRITE_FLAGS = [cv2.IMWRITE_JPEG_QUALITY, 85]


@dataclass
class FrameRecord:
    frame_number: int
    frame: np.ndarray
    roi_frame: np.ndarray
    analysis_roi: np.ndarray
    sharpness: float


@dataclass
class CandidateScore:
    record: FrameRecord
    local_motion: float
    sharpness: float
    fallback_score: float


class StableWindowTracker:
    def __init__(
        self,
        *,
        low_motion_threshold: float,
        fallback_weight: float,
    ) -> None:
        self.low_motion_threshold = low_motion_threshold
        self.fallback_weight = fallback_weight
        self.duration_frames = 0
        self.buffer: deque[FrameRecord] = deque(maxlen=3)
        self.best_low_motion: CandidateScore | None = None
        self.best_fallback: CandidateScore | None = None

    def append(self, record: FrameRecord) -> None:
        self.duration_frames += 1
        self.buffer.append(record)
        if len(self.buffer) < 3:
            return

        prev_record, mid_record, next_record = self.buffer
        local_motion = _local_motion(
            prev_record.analysis_roi,
            mid_record.analysis_roi,
            next_record.analysis_roi,
        )
        candidate = CandidateScore(
            record=mid_record,
            local_motion=local_motion,
            sharpness=mid_record.sharpness,
            fallback_score=mid_record.sharpness - (self.fallback_weight * local_motion),
        )

        if (
            local_motion <= self.low_motion_threshold
            and _prefer_low_motion_candidate(candidate, self.best_low_motion)
        ):
            self.best_low_motion = candidate

        if _prefer_fallback_candidate(candidate, self.best_fallback):
            self.best_fallback = candidate

    def select(self) -> tuple[CandidateScore | None, bool]:
        if self.best_low_motion is not None:
            return self.best_low_motion, False
        if self.best_fallback is not None:
            return self.best_fallback, True
        return None, False

    def clone(self) -> StableWindowTracker:
        tracker = StableWindowTracker(
            low_motion_threshold=self.low_motion_threshold,
            fallback_weight=self.fallback_weight,
        )
        tracker.duration_frames = self.duration_frames
        tracker.buffer = deque(self.buffer, maxlen=self.buffer.maxlen)
        tracker.best_low_motion = self.best_low_motion
        tracker.best_fallback = self.best_fallback
        return tracker


def _staged_output_dir(output_dir: Path) -> Path:
    staged_dir = output_dir.parent / f".{output_dir.name}.extracting-{uuid.uuid4().hex}"
    if staged_dir.exists():
        shutil.rmtree(staged_dir, ignore_errors=True)
    return staged_dir


def _swap_output_dir(staged_dir: Path, output_dir: Path) -> None:
    backup_dir: Path | None = None
    if output_dir.exists():
        backup_dir = output_dir.parent / f".{output_dir.name}.previous-{uuid.uuid4().hex}"
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
        output_dir.replace(backup_dir)

    try:
        staged_dir.replace(output_dir)
    except Exception:
        if backup_dir is not None and backup_dir.exists() and not output_dir.exists():
            backup_dir.replace(output_dir)
        raise
    else:
        if backup_dir is not None and backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)


def extract_frames(
    video_path: str | Path,
    video_id: str,
    output_dir: str | Path | None = None,
) -> list[dict]:
    """
    Extract one best frame per stable card window from a video.

    Returns a list of dicts with keys including:
    frame_number, image_path, sequence_index, needs_review, extraction_confidence.
    """
    config = get_config()
    frame_cfg = config.get("frame_extraction", {})
    video_path = str(video_path)

    if output_dir is None:
        output_dir = Path(config["storage"]["frames_dir"]) / video_id
    output_dir = Path(output_dir)
    staged_output_dir = _staged_output_dir(output_dir)
    staged_output_dir.mkdir(parents=True, exist_ok=True)
    rejected_blur_dir = staged_output_dir / "rejected_blur"
    rejected_blur_dir.mkdir(parents=True, exist_ok=True)

    decisions_path = staged_output_dir / "extraction_decisions.jsonl"
    manifest_path = staged_output_dir / "extraction_manifest.json"

    analysis_width = max(32, int(frame_cfg.get("analysis_width", 320)))
    margin_x = float(frame_cfg.get("roi_margin_x", 0.20))
    margin_top = float(frame_cfg.get("roi_margin_top", 0.15))
    margin_bottom = float(frame_cfg.get("roi_margin_bottom", 0.20))
    enter_motion_threshold = float(frame_cfg.get("enter_motion_threshold", 12.0))
    enter_motion_frames = max(1, int(frame_cfg.get("enter_motion_consecutive_frames", 2)))
    exit_motion_threshold = float(frame_cfg.get("exit_motion_threshold", 6.0))
    exit_motion_frames = max(1, int(frame_cfg.get("exit_motion_consecutive_frames", 5)))
    min_emit_stable_frames = max(1, int(frame_cfg.get("min_emit_stable_frames", 10)))
    low_confidence_stable_frames = max(
        min_emit_stable_frames,
        int(frame_cfg.get("low_confidence_stable_frames", 12)),
    )
    low_motion_candidate_threshold = float(
        frame_cfg.get("low_motion_candidate_threshold", exit_motion_threshold)
    )
    fallback_motion_weight = float(frame_cfg.get("fallback_motion_weight", 4.0))
    missed_insert_check_start_frames = max(
        min_emit_stable_frames,
        int(frame_cfg.get("missed_insert_check_start_frames", 18)),
    )
    missed_insert_check_interval_frames = max(
        1,
        int(frame_cfg.get("missed_insert_check_interval_frames", 6)),
    )
    missed_insert_cell_threshold = float(
        frame_cfg.get("missed_insert_cell_threshold", 8.0)
    )
    missed_insert_required_cells = max(
        1,
        int(frame_cfg.get("missed_insert_required_cells", 2)),
    )
    missed_insert_required_checks = max(
        1,
        int(frame_cfg.get("missed_insert_required_checks", 2)),
    )
    missed_insert_seed_recent_frames = max(
        missed_insert_check_interval_frames,
        int(
            frame_cfg.get(
                "missed_insert_seed_recent_frames",
                missed_insert_check_interval_frames,
            )
        ),
    )
    blur_threshold = float(
        frame_cfg.get("blur_threshold", frame_cfg.get("blank_threshold", 50.0))
    )
    dedup_enabled = bool(frame_cfg.get("dedup_enabled", True))
    dedup_hamming_threshold = int(frame_cfg.get("dedup_hamming_threshold", 6))
    dhash_size = max(2, int(frame_cfg.get("dhash_size", 8)))

    cap: cv2.VideoCapture | None = None
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

        cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
        rotation = cap.get(cv2.CAP_PROP_ORIENTATION_META)
        if rotation:
            logger.info("Video has rotation metadata: %s°, auto-correcting frames", rotation)

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        decision_counts = {
            "accepted": 0,
            "rejected_blur": 0,
            "rejected_dedup": 0,
            "rejected_short_stable": 0,
        }
        results: list[dict[str, Any]] = []
        accepted_frames: list[dict[str, Any]] = []
        candidate_count = 0
        stable_windows_total = 0
        next_sequence = 1
        window_index = 0

        state = "idle"
        prev_center_analysis: np.ndarray | None = None
        gray_motion_streak = 0
        low_motion_streak = 0
        low_motion_seed: deque[FrameRecord] = deque(maxlen=exit_motion_frames)
        stable_window: StableWindowTracker | None = None
        backstop_anchor_analysis: np.ndarray | None = None
        backstop_anchor_window: StableWindowTracker | None = None
        backstop_frames_since_anchor = 0
        backstop_positive_checks = 0
        backstop_recent_records: deque[FrameRecord] = deque(
            maxlen=missed_insert_seed_recent_frames
        )
        backstop_pending_window: StableWindowTracker | None = None

        last_accepted_hash: np.ndarray | None = None
        last_accepted_frame_number: int | None = None

        frame_number = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            resized_gray = _prepare_analysis_gray(
                frame,
                analysis_width=analysis_width,
            )
            analysis_roi = _crop_roi(
                resized_gray,
                margin_x=margin_x,
                margin_top=margin_top,
                margin_bottom=margin_bottom,
            )
            if prev_center_analysis is None:
                prev_center_analysis = analysis_roi
                frame_number += 1
                continue

            gray_motion = _mad(prev_center_analysis, analysis_roi)
            prev_center_analysis = analysis_roi

            is_high_motion = gray_motion >= enter_motion_threshold
            gray_motion_streak = (gray_motion_streak + 1) if is_high_motion else 0
            is_low_motion = gray_motion <= exit_motion_threshold
            low_motion_streak = (low_motion_streak + 1) if is_low_motion else 0
            has_enter_motion = gray_motion_streak >= enter_motion_frames

            if state == "idle":
                if has_enter_motion:
                    state = "transitioning"
                    low_motion_streak = 0
                    low_motion_seed.clear()
                frame_number += 1
                continue

            if state == "transitioning":
                if is_low_motion:
                    low_motion_seed.append(
                        _make_frame_record(
                            frame_number=frame_number,
                            frame=frame,
                            analysis_roi=analysis_roi,
                            margin_x=margin_x,
                            margin_top=margin_top,
                            margin_bottom=margin_bottom,
                        )
                    )
                    if low_motion_streak >= exit_motion_frames:
                        stable_window = StableWindowTracker(
                            low_motion_threshold=low_motion_candidate_threshold,
                            fallback_weight=fallback_motion_weight,
                        )
                        for seed_record in low_motion_seed:
                            stable_window.append(seed_record)
                        state = "stable"
                        gray_motion_streak = 0
                        backstop_anchor_analysis = low_motion_seed[-1].analysis_roi.copy()
                        backstop_anchor_window = stable_window.clone()
                        backstop_frames_since_anchor = 0
                        backstop_positive_checks = 0
                        backstop_recent_records.clear()
                        backstop_pending_window = None
                else:
                    low_motion_seed.clear()

                frame_number += 1
                continue

            if stable_window is None:
                raise RuntimeError("Stable window tracker missing while in stable state")

            if has_enter_motion:
                stable_windows_total += 1
                window_index += 1
                candidate_count += 1
                next_sequence, last_accepted_hash, last_accepted_frame_number = _process_window_end(
                    tracker=stable_window,
                    stable_index=window_index,
                    eof=False,
                    min_emit_stable_frames=min_emit_stable_frames,
                    low_confidence_stable_frames=low_confidence_stable_frames,
                    blur_threshold=blur_threshold,
                    dedup_enabled=dedup_enabled,
                    dedup_hamming_threshold=dedup_hamming_threshold,
                    dhash_size=dhash_size,
                    next_sequence=next_sequence,
                    decisions_path=decisions_path,
                    decision_counts=decision_counts,
                    staged_output_dir=staged_output_dir,
                    final_output_dir=output_dir,
                    rejected_blur_dir=rejected_blur_dir,
                    video_id=video_id,
                    results=results,
                    accepted_frames=accepted_frames,
                    last_accepted_hash=last_accepted_hash,
                    last_accepted_frame_number=last_accepted_frame_number,
                )
                stable_window = None
                state = "transitioning"
                low_motion_streak = 0
                low_motion_seed.clear()
                backstop_anchor_analysis = None
                backstop_anchor_window = None
                backstop_frames_since_anchor = 0
                backstop_positive_checks = 0
                backstop_recent_records.clear()
                backstop_pending_window = None
                frame_number += 1
                continue

            record = _make_frame_record(
                frame_number=frame_number,
                frame=frame,
                analysis_roi=analysis_roi,
                margin_x=margin_x,
                margin_top=margin_top,
                margin_bottom=margin_bottom,
            )
            stable_window.append(record)
            backstop_recent_records.append(record)
            backstop_frames_since_anchor += 1
            if backstop_pending_window is not None:
                backstop_pending_window.append(record)

            if (
                backstop_anchor_analysis is not None
                and backstop_anchor_window is not None
                and stable_window.duration_frames >= missed_insert_check_start_frames
                and backstop_frames_since_anchor >= missed_insert_check_interval_frames
                and (
                    backstop_frames_since_anchor % missed_insert_check_interval_frames == 0
                )
            ):
                has_localized_change = _has_localized_grid_change(
                    backstop_anchor_analysis,
                    analysis_roi,
                    cell_threshold=missed_insert_cell_threshold,
                    required_cells=missed_insert_required_cells,
                )
                if has_localized_change:
                    if backstop_positive_checks == 0:
                        backstop_pending_window = StableWindowTracker(
                            low_motion_threshold=low_motion_candidate_threshold,
                            fallback_weight=fallback_motion_weight,
                        )
                        for recent_record in backstop_recent_records:
                            backstop_pending_window.append(recent_record)
                    backstop_positive_checks += 1

                    if (
                        backstop_positive_checks >= missed_insert_required_checks
                        and backstop_pending_window is not None
                    ):
                        stable_windows_total += 1
                        window_index += 1
                        candidate_count += 1
                        next_sequence, last_accepted_hash, last_accepted_frame_number = _process_window_end(
                            tracker=backstop_anchor_window,
                            stable_index=window_index,
                            eof=False,
                            min_emit_stable_frames=min_emit_stable_frames,
                            low_confidence_stable_frames=low_confidence_stable_frames,
                            blur_threshold=blur_threshold,
                            dedup_enabled=dedup_enabled,
                            dedup_hamming_threshold=dedup_hamming_threshold,
                            dhash_size=dhash_size,
                            next_sequence=next_sequence,
                            decisions_path=decisions_path,
                            decision_counts=decision_counts,
                            staged_output_dir=staged_output_dir,
                            final_output_dir=output_dir,
                            rejected_blur_dir=rejected_blur_dir,
                            video_id=video_id,
                            results=results,
                            accepted_frames=accepted_frames,
                            last_accepted_hash=last_accepted_hash,
                            last_accepted_frame_number=last_accepted_frame_number,
                        )
                        stable_window = backstop_pending_window
                        backstop_anchor_analysis = analysis_roi.copy()
                        backstop_anchor_window = stable_window.clone()
                        backstop_frames_since_anchor = 0
                        backstop_positive_checks = 0
                        backstop_recent_records.clear()
                        backstop_pending_window = None
                        frame_number += 1
                        continue
                else:
                    backstop_anchor_analysis = analysis_roi.copy()
                    backstop_anchor_window = stable_window.clone()
                    backstop_frames_since_anchor = 0
                    backstop_positive_checks = 0
                    backstop_recent_records.clear()
                    backstop_pending_window = None

            frame_number += 1

        if state == "stable" and stable_window is not None:
            stable_windows_total += 1
            window_index += 1
            candidate_count += 1
            next_sequence, last_accepted_hash, last_accepted_frame_number = _process_window_end(
                tracker=stable_window,
                stable_index=window_index,
                eof=True,
                min_emit_stable_frames=min_emit_stable_frames,
                low_confidence_stable_frames=low_confidence_stable_frames,
                blur_threshold=blur_threshold,
                dedup_enabled=dedup_enabled,
                dedup_hamming_threshold=dedup_hamming_threshold,
                dhash_size=dhash_size,
                next_sequence=next_sequence,
                decisions_path=decisions_path,
                decision_counts=decision_counts,
                staged_output_dir=staged_output_dir,
                final_output_dir=output_dir,
                rejected_blur_dir=rejected_blur_dir,
                video_id=video_id,
                results=results,
                accepted_frames=accepted_frames,
                last_accepted_hash=last_accepted_hash,
                last_accepted_frame_number=last_accepted_frame_number,
            )

        manifest = {
            "video_id": video_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "strategy": {
                "detector": "hysteresis_state_machine",
                "states": ["idle", "transitioning", "stable"],
            },
            "thresholds": {
                "analysis_width": analysis_width,
                "roi_margin_x": margin_x,
                "roi_margin_top": margin_top,
                "roi_margin_bottom": margin_bottom,
                "enter_motion_threshold": enter_motion_threshold,
                "enter_motion_consecutive_frames": enter_motion_frames,
                "exit_motion_threshold": exit_motion_threshold,
                "exit_motion_consecutive_frames": exit_motion_frames,
                "min_emit_stable_frames": min_emit_stable_frames,
                "low_confidence_stable_frames": low_confidence_stable_frames,
                "low_motion_candidate_threshold": low_motion_candidate_threshold,
                "fallback_motion_weight": fallback_motion_weight,
                "missed_insert_check_start_frames": missed_insert_check_start_frames,
                "missed_insert_check_interval_frames": missed_insert_check_interval_frames,
                "missed_insert_cell_threshold": missed_insert_cell_threshold,
                "missed_insert_required_cells": missed_insert_required_cells,
                "missed_insert_required_checks": missed_insert_required_checks,
                "missed_insert_seed_recent_frames": missed_insert_seed_recent_frames,
                "blur_threshold": blur_threshold,
                "dedup_enabled": dedup_enabled,
                "dedup_hamming_threshold": dedup_hamming_threshold,
                "dhash_size": dhash_size,
            },
            "counts": {
                **decision_counts,
                "total_frames": total_frames,
                "stable_windows_total": stable_windows_total,
                "candidate_count": candidate_count,
            },
            "accepted_frames": accepted_frames,
            "files": {
                "decisions_jsonl": str(output_dir / "extraction_decisions.jsonl"),
                "rejected_blur_dir": str(output_dir / "rejected_blur"),
                "frames_dir": str(output_dir),
            },
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        _swap_output_dir(staged_output_dir, output_dir)
        return results
    except Exception:
        shutil.rmtree(staged_output_dir, ignore_errors=True)
        raise
    finally:
        if cap is not None:
            cap.release()


def _make_frame_record(
    *,
    frame_number: int,
    frame: np.ndarray,
    analysis_roi: np.ndarray,
    margin_x: float,
    margin_top: float,
    margin_bottom: float,
) -> FrameRecord:
    roi_frame = _crop_roi(
        frame,
        margin_x=margin_x,
        margin_top=margin_top,
        margin_bottom=margin_bottom,
    )
    return FrameRecord(
        frame_number=frame_number,
        frame=frame.copy(),
        roi_frame=roi_frame.copy(),
        analysis_roi=analysis_roi.copy(),
        sharpness=compute_sharpness(roi_frame),
    )


def _prepare_analysis_gray(
    frame: np.ndarray,
    *,
    analysis_width: int,
) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    scale = analysis_width / gray.shape[1]
    target_height = max(1, int(round(gray.shape[0] * scale)))
    return cv2.resize(gray, (analysis_width, target_height), interpolation=cv2.INTER_AREA)


def _crop_roi(
    image: np.ndarray,
    *,
    margin_x: float,
    margin_top: float,
    margin_bottom: float,
) -> np.ndarray:
    height, width = image.shape[:2]
    left = min(width - 1, max(0, int(round(width * margin_x))))
    right = max(left + 1, min(width, width - int(round(width * margin_x))))
    top = min(height - 1, max(0, int(round(height * margin_top))))
    bottom = max(top + 1, min(height, height - int(round(height * margin_bottom))))
    return image[top:bottom, left:right]


def _mad(previous: np.ndarray, current: np.ndarray) -> float:
    return float(np.mean(np.abs(previous.astype(np.float32) - current.astype(np.float32))))


def _has_localized_grid_change(
    reference: np.ndarray,
    current: np.ndarray,
    *,
    cell_threshold: float,
    required_cells: int,
    rows: int = 4,
    cols: int = 4,
) -> bool:
    changed_cells = 0
    height, width = reference.shape[:2]
    row_edges = np.linspace(0, height, rows + 1, dtype=int)
    col_edges = np.linspace(0, width, cols + 1, dtype=int)

    for row_index in range(rows):
        for col_index in range(cols):
            cell_reference = reference[
                row_edges[row_index]:row_edges[row_index + 1],
                col_edges[col_index]:col_edges[col_index + 1],
            ]
            cell_current = current[
                row_edges[row_index]:row_edges[row_index + 1],
                col_edges[col_index]:col_edges[col_index + 1],
            ]
            if _mad(cell_reference, cell_current) >= cell_threshold:
                changed_cells += 1
                if changed_cells >= required_cells:
                    return True

    return False


def _local_motion(previous: np.ndarray, current: np.ndarray, nxt: np.ndarray) -> float:
    return (_mad(previous, current) + _mad(current, nxt)) / 2.0


def _prefer_low_motion_candidate(
    candidate: CandidateScore,
    current: CandidateScore | None,
) -> bool:
    if current is None:
        return True
    if candidate.local_motion != current.local_motion:
        return candidate.local_motion < current.local_motion
    if candidate.sharpness != current.sharpness:
        return candidate.sharpness > current.sharpness
    return candidate.record.frame_number < current.record.frame_number


def _prefer_fallback_candidate(
    candidate: CandidateScore,
    current: CandidateScore | None,
) -> bool:
    if current is None:
        return True
    if candidate.fallback_score != current.fallback_score:
        return candidate.fallback_score > current.fallback_score
    if candidate.local_motion != current.local_motion:
        return candidate.local_motion < current.local_motion
    if candidate.sharpness != current.sharpness:
        return candidate.sharpness > current.sharpness
    return candidate.record.frame_number < current.record.frame_number


def _process_window_end(
    *,
    tracker: StableWindowTracker,
    stable_index: int,
    eof: bool,
    min_emit_stable_frames: int,
    low_confidence_stable_frames: int,
    blur_threshold: float,
    dedup_enabled: bool,
    dedup_hamming_threshold: int,
    dhash_size: int,
    next_sequence: int,
    decisions_path: Path,
    decision_counts: dict[str, int],
    staged_output_dir: Path,
    final_output_dir: Path,
    rejected_blur_dir: Path,
    video_id: str,
    results: list[dict[str, Any]],
    accepted_frames: list[dict[str, Any]],
    last_accepted_hash: np.ndarray | None,
    last_accepted_frame_number: int | None,
) -> tuple[int, np.ndarray | None, int | None]:
    window = _finalize_stable_window(
        tracker,
        stable_index=stable_index,
        eof=eof,
        min_emit_stable_frames=min_emit_stable_frames,
        low_confidence_stable_frames=low_confidence_stable_frames,
        blur_threshold=blur_threshold,
    )

    if window["decision"] == "rejected_short_stable":
        decision_counts["rejected_short_stable"] += 1
        _append_decision(decisions_path, {
            "decision": "rejected_short_stable",
            "video_id": video_id,
            "segment_index": stable_index,
            "stable_duration_frames": window["stable_duration_frames"],
            "reason": window["reason"],
        })
        return next_sequence, last_accepted_hash, last_accepted_frame_number

    if window["selected_sharpness"] < blur_threshold:
        blur_filename = f"segment_{stable_index:04d}_frame_{window['frame_number']:06d}.jpg"
        staged_blur_path = rejected_blur_dir / blur_filename
        final_blur_path = final_output_dir / "rejected_blur" / blur_filename
        cv2.imwrite(str(staged_blur_path), window["frame"], _JPEG_WRITE_FLAGS)

        decision_counts["rejected_blur"] += 1
        _append_decision(decisions_path, {
            "decision": "rejected_blur",
            "video_id": video_id,
            "segment_index": stable_index,
            "frame_number": window["frame_number"],
            "stable_duration_frames": window["stable_duration_frames"],
            "selected_motion_score": window["selected_motion_score"],
            "selected_sharpness": window["selected_sharpness"],
            "sharpness": window["selected_sharpness"],
            "needs_review": window["needs_review"],
            "extraction_confidence": window["extraction_confidence"],
            "image_path": str(final_blur_path),
            "threshold": blur_threshold,
            "reason": "below_blur_threshold",
        })
        return next_sequence, last_accepted_hash, last_accepted_frame_number

    current_hash = compute_dhash(window["roi_frame"], hash_size=dhash_size)
    duplicate_distance: int | None = None
    if dedup_enabled and last_accepted_hash is not None:
        duplicate_distance = hamming_distance(last_accepted_hash, current_hash)
        if duplicate_distance < dedup_hamming_threshold:
            decision_counts["rejected_dedup"] += 1
            _append_decision(decisions_path, {
                "decision": "rejected_dedup",
                "video_id": video_id,
                "segment_index": stable_index,
                "frame_number": window["frame_number"],
                "stable_duration_frames": window["stable_duration_frames"],
                "selected_motion_score": window["selected_motion_score"],
                "selected_sharpness": window["selected_sharpness"],
                "sharpness": window["selected_sharpness"],
                "needs_review": window["needs_review"],
                "extraction_confidence": window["extraction_confidence"],
                "duplicate_distance": duplicate_distance,
                "duplicate_of_frame_number": last_accepted_frame_number,
                "reason": "adjacent_roi_duplicate",
            })
            return next_sequence, last_accepted_hash, last_accepted_frame_number

    filename = f"card_{next_sequence:04d}.jpg"
    staged_image_path = staged_output_dir / filename
    final_image_path = final_output_dir / filename
    cv2.imwrite(str(staged_image_path), window["frame"], _JPEG_WRITE_FLAGS)

    accepted_item = {
        "frame_number": window["frame_number"],
        "image_path": str(final_image_path),
        "sequence_index": next_sequence,
        "needs_review": window["needs_review"],
        "extraction_confidence": window["extraction_confidence"],
        "stable_duration_frames": window["stable_duration_frames"],
        "selected_motion_score": window["selected_motion_score"],
        "selected_sharpness": window["selected_sharpness"],
        "duplicate_distance": duplicate_distance,
    }
    results.append(dict(accepted_item))
    accepted_frames.append(dict(accepted_item))
    decision_counts["accepted"] += 1
    _append_decision(decisions_path, {
        "decision": "accepted",
        "video_id": video_id,
        "segment_index": stable_index,
        "sequence_index": next_sequence,
        "frame_number": window["frame_number"],
        "image_path": str(final_image_path),
        "stable_duration_frames": window["stable_duration_frames"],
        "selected_motion_score": window["selected_motion_score"],
        "selected_sharpness": window["selected_sharpness"],
        "sharpness": window["selected_sharpness"],
        "needs_review": window["needs_review"],
        "extraction_confidence": window["extraction_confidence"],
        "duplicate_distance": duplicate_distance,
        "reason": "selected_for_ocr",
    })

    next_hash = current_hash if dedup_enabled else last_accepted_hash
    next_last_frame_number = window["frame_number"] if dedup_enabled else last_accepted_frame_number
    return next_sequence + 1, next_hash, next_last_frame_number


def _finalize_stable_window(
    tracker: StableWindowTracker,
    *,
    stable_index: int,
    eof: bool,
    min_emit_stable_frames: int,
    low_confidence_stable_frames: int,
    blur_threshold: float,
) -> dict[str, Any]:
    if tracker.duration_frames < min_emit_stable_frames:
        return {
            "decision": "rejected_short_stable",
            "segment_index": stable_index,
            "stable_duration_frames": tracker.duration_frames,
            "reason": "stable_window_too_short",
        }

    selected, fallback_used = tracker.select()
    if selected is None:
        return {
            "decision": "rejected_short_stable",
            "segment_index": stable_index,
            "stable_duration_frames": tracker.duration_frames,
            "reason": "stable_window_missing_candidate",
        }

    needs_review = (
        tracker.duration_frames < low_confidence_stable_frames
        or eof
        or fallback_used
        or selected.sharpness < blur_threshold
    )
    return {
        "decision": "candidate",
        "segment_index": stable_index,
        "frame_number": selected.record.frame_number,
        "frame": selected.record.frame,
        "roi_frame": selected.record.roi_frame,
        "stable_duration_frames": tracker.duration_frames,
        "selected_motion_score": selected.local_motion,
        "selected_sharpness": selected.sharpness,
        "needs_review": needs_review,
        "extraction_confidence": "low" if needs_review else "high",
        "fallback_used": fallback_used,
    }


def _append_decision(path: Path, decision: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(decision, ensure_ascii=False))
        f.write("\n")
