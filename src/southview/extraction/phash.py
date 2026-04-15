"""Perceptual hashing helpers for frame deduplication."""

from __future__ import annotations

import cv2
import numpy as np


def compute_dhash(
    frame: np.ndarray,
    *,
    hash_size: int = 8,
) -> np.ndarray:
    """
    Compute a difference hash for an image frame.

    Returns a boolean array of shape (hash_size, hash_size).
    """
    if hash_size < 2:
        raise ValueError("hash_size must be >= 2")

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    return resized[:, 1:] > resized[:, :-1]


def compute_phash(
    frame: np.ndarray,
    *,
    hash_size: int = 8,
    highfreq_factor: int = 4,
) -> np.ndarray:
    """
    Compute a perceptual hash for an image frame.

    Returns a boolean array of shape (hash_size, hash_size).
    """
    if hash_size < 2:
        raise ValueError("hash_size must be >= 2")
    if highfreq_factor < 1:
        raise ValueError("highfreq_factor must be >= 1")

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    size = hash_size * highfreq_factor
    resized = cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(resized))
    low_freq = dct[:hash_size, :hash_size]

    # Ignore the DC component when computing threshold for robustness.
    median = np.median(low_freq[1:, 1:])
    return low_freq > median


def hamming_distance(hash_a: np.ndarray, hash_b: np.ndarray) -> int:
    """Compute Hamming distance between two boolean hash arrays."""
    if hash_a.shape != hash_b.shape:
        raise ValueError("Hashes must have the same shape")
    return int(np.count_nonzero(hash_a != hash_b))
