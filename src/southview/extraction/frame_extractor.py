"""Main frame extraction orchestrator."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from southview.config import get_config
from southview.extraction.phash import compute_phash, hamming_distance
from southview.extraction.scene_detect import detect_transitions
from southview.extraction.sharpness import compute_sharpness

logger = logging.getLogger(__name__)


def extract_frames(
    video_path: str | Path,
    video_id: str,
    output_dir: str | Path | None = None,
) -> list[dict]:
    """
    Extract one best frame per card from a video.

    Returns a list of dicts with keys: frame_number, image_path, sequence_index.
    """
    config = get_config()
    video_path = str(video_path)

    if output_dir is None:
        output_dir = Path(config["storage"]["frames_dir"]) / video_id
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rejected_blur_dir = output_dir / "rejected_blur"
    rejected_blur_dir.mkdir(parents=True, exist_ok=True)

    decisions_path = output_dir / "extraction_decisions.jsonl"
    manifest_path = output_dir / "extraction_manifest.json"
    if decisions_path.exists():
        decisions_path.unlink()
    if manifest_path.exists():
        manifest_path.unlink()

    transitions = detect_transitions(video_path)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    # Auto-rotate frames based on video rotation metadata (e.g. phone videos)
    cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
    rotation = cap.get(cv2.CAP_PROP_ORIENTATION_META)
    if rotation:
        logger.info(f"Video has rotation metadata: {rotation}°, auto-correcting frames")

    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Build segments: ranges between transitions
        boundaries = [0] + transitions + [total_frames]
        segments = [
            (boundaries[i], boundaries[i + 1]) for i in range(len(boundaries) - 1)
        ]

        frame_cfg = config.get("frame_extraction", {})
        min_stable = int(frame_cfg.get("min_stable_frames", 5))
        blur_threshold = float(
            frame_cfg.get("blur_threshold", frame_cfg.get("blank_threshold", 50.0))
        )
        dedup_enabled = bool(frame_cfg.get("dedup_enabled", True))
        dedup_hamming_threshold = int(frame_cfg.get("dedup_hamming_threshold", 8))
        hash_size = int(frame_cfg.get("hash_size", 8))
        highfreq_factor = int(frame_cfg.get("highfreq_factor", 4))

        candidate_count = 0
        decision_counts = {
            "accepted": 0,
            "rejected_blur": 0,
            "rejected_dedup": 0,
        }
        current_group: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        next_sequence = 1

        for seg_idx, (start, end) in enumerate(segments):
            segment_index = seg_idx + 1
            if (end - start) < min_stable:
                continue

            best_frame, best_frame_num = _find_best_frame(cap, start, end)
            if best_frame is None:
                continue

            sharpness = compute_sharpness(best_frame)
            if sharpness < blur_threshold:
                blur_filename = (
                    f"segment_{segment_index:04d}_frame_{best_frame_num:06d}.jpg"
                )
                blur_path = rejected_blur_dir / blur_filename
                cv2.imwrite(str(blur_path), best_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

                decision_counts["rejected_blur"] += 1
                _append_decision(decisions_path, {
                    "decision": "rejected_blur",
                    "video_id": video_id,
                    "segment_index": segment_index,
                    "frame_number": best_frame_num,
                    "sharpness": sharpness,
                    "threshold": blur_threshold,
                    "image_path": str(blur_path),
                    "reason": "below_blur_threshold",
                })
                continue

            candidate = {
                "segment_index": segment_index,
                "frame_number": best_frame_num,
                "sharpness": sharpness,
                "frame": best_frame,
                "hash": compute_phash(
                    best_frame,
                    hash_size=hash_size,
                    highfreq_factor=highfreq_factor,
                ),
            }
            candidate_count += 1

            if not current_group:
                current_group = [candidate]
                continue

            is_duplicate = (
                dedup_enabled
                and hamming_distance(current_group[-1]["hash"], candidate["hash"])
                <= dedup_hamming_threshold
            )
            if is_duplicate:
                current_group.append(candidate)
                continue

            next_sequence = _persist_candidate_group(
                group=current_group,
                next_sequence=next_sequence,
                output_dir=output_dir,
                decisions_path=decisions_path,
                decision_counts=decision_counts,
                video_id=video_id,
                results=results,
            )
            current_group = [candidate]

        if current_group:
            next_sequence = _persist_candidate_group(
                group=current_group,
                next_sequence=next_sequence,
                output_dir=output_dir,
                decisions_path=decisions_path,
                decision_counts=decision_counts,
                video_id=video_id,
                results=results,
            )

        manifest = {
            "video_id": video_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "thresholds": {
                "blur_threshold": blur_threshold,
                "dedup_enabled": dedup_enabled,
                "dedup_hamming_threshold": dedup_hamming_threshold,
                "hash_size": hash_size,
                "highfreq_factor": highfreq_factor,
            },
            "counts": {
                **decision_counts,
                "segments_total": len(segments),
                "candidate_count": candidate_count,
            },
            "files": {
                "decisions_jsonl": str(decisions_path),
                "rejected_blur_dir": str(rejected_blur_dir),
                "frames_dir": str(output_dir),
            },
        }
        manifest_path.write_text(json.dumps(manifest, indent=2))
        return results
    finally:
        cap.release()


def _find_best_frame(
    cap: cv2.VideoCapture, start: int, end: int
) -> tuple[np.ndarray | None, int]:
    """Find the sharpest frame in a range."""
    best_sharpness = -1.0
    best_frame = None
    best_num = start

    # Sample the middle 60% of the segment to avoid transition edges
    margin = int((end - start) * 0.2)
    sample_start = start + margin
    sample_end = end - margin

    cap.set(cv2.CAP_PROP_POS_FRAMES, sample_start)

    for frame_num in range(sample_start, sample_end):
        ret, frame = cap.read()
        if not ret:
            break
        sharpness = compute_sharpness(frame)
        if sharpness > best_sharpness:
            best_sharpness = sharpness
            best_frame = frame.copy()
            best_num = frame_num

    return best_frame, best_num


def _append_decision(path: Path, decision: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(decision, ensure_ascii=False))
        f.write("\n")


def _persist_candidate_group(
    *,
    group: list[dict[str, Any]],
    next_sequence: int,
    output_dir: Path,
    decisions_path: Path,
    decision_counts: dict[str, int],
    video_id: str,
    results: list[dict[str, Any]],
) -> int:
    winner = max(group, key=lambda item: (item["sharpness"], -item["frame_number"]))

    filename = f"card_{next_sequence:04d}.jpg"
    image_path = output_dir / filename
    cv2.imwrite(str(image_path), winner["frame"], [cv2.IMWRITE_JPEG_QUALITY, 85])

    accepted_item = {
        "frame_number": winner["frame_number"],
        "image_path": str(image_path),
        "sequence_index": next_sequence,
    }
    results.append(accepted_item)
    decision_counts["accepted"] += 1
    _append_decision(decisions_path, {
        "decision": "accepted",
        "video_id": video_id,
        "segment_index": winner["segment_index"],
        "sequence_index": next_sequence,
        "frame_number": winner["frame_number"],
        "sharpness": winner["sharpness"],
        "image_path": str(image_path),
        "reason": "selected_for_ocr",
    })

    for item in group:
        if item is winner:
            continue
        decision_counts["rejected_dedup"] += 1
        _append_decision(decisions_path, {
            "decision": "rejected_dedup",
            "video_id": video_id,
            "segment_index": item["segment_index"],
            "frame_number": item["frame_number"],
            "sharpness": item["sharpness"],
            "duplicate_of_frame_number": winner["frame_number"],
            "reason": "adjacent_perceptual_duplicate",
        })

    return next_sequence + 1
