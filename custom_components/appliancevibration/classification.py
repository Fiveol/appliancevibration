"""Cycle classification for the ApplianceVibration integration.

A cycle is described by a small feature vector (duration, mean/max/std of the
vibration magnitude). Each program accumulates statistics over the cycles the
user labels with it. A new cycle is matched against the known programs with a
weighted normalized Euclidean distance; the match quality is returned as a
similarity in [0, 1].
"""

from __future__ import annotations

import math
from typing import Any

from .const import (
    CYC_DURATION,
    CYC_MAG_MAX,
    CYC_MAG_MEAN,
    CYC_MAG_STD,
    FEATURES,
    PROG_STATS,
)

# Feature weights: how much each dimension counts when matching.
WEIGHTS: dict[str, float] = {
    CYC_DURATION: 1.0,
    CYC_MAG_MEAN: 2.0,
    CYC_MAG_MAX: 1.0,
    CYC_MAG_STD: 1.0,
}

_EPSILON = 1e-6


def cycle_features(cycle: dict[str, Any]) -> dict[str, float]:
    """Extract the feature vector of a completed cycle."""
    return {feature: float(cycle.get(feature, 0.0) or 0.0) for feature in FEATURES}


def add_sample(
    program: dict[str, Any],
    cycle: dict[str, Any] | None = None,
    features: dict[str, float] | None = None,
) -> None:
    """Fold a labeled cycle into a program's statistics."""
    stats = program.setdefault(PROG_STATS, {})
    sample = cycle_features(cycle) if cycle is not None else features or {}
    count = int(stats.get("count", 0))

    if count == 0:
        for feature in FEATURES:
            stats[f"{feature}_min"] = sample[feature]
            stats[f"{feature}_max"] = sample[feature]
        mean = {feature: sample[feature] for feature in FEATURES}
    else:
        mean = {
            feature: (
                float(stats.get(f"{feature}_mean", 0.0)) * count + sample[feature]
            )
            / (count + 1)
            for feature in FEATURES
        }
        for feature in FEATURES:
            stats[f"{feature}_min"] = min(
                float(stats.get(f"{feature}_min", sample[feature])), sample[feature]
            )
            stats[f"{feature}_max"] = max(
                float(stats.get(f"{feature}_max", sample[feature])), sample[feature]
            )

    stats["count"] = count + 1
    for feature in FEATURES:
        stats[f"{feature}_mean"] = mean[feature]
    program["samples"] = count + 1


def remove_sample(
    program: dict[str, Any],
    cycle: dict[str, Any] | None = None,
    features: dict[str, float] | None = None,
) -> None:
    """Remove a cycle's contribution from a program's statistics."""
    stats = program.get(PROG_STATS, {})
    sample = cycle_features(cycle) if cycle is not None else features or {}
    count = int(stats.get("count", 0))
    if count <= 1:
        stats.clear()
        program["samples"] = 0
        return
    mean = {
        feature: (float(stats.get(f"{feature}_mean", 0.0)) * count - sample[feature])
        / (count - 1)
        for feature in FEATURES
    }
    stats["count"] = count - 1
    for feature in FEATURES:
        stats[f"{feature}_mean"] = mean[feature]
    program["samples"] = count - 1


def _means(stats: dict[str, Any]) -> dict[str, float]:
    """Return the mean vector of a program."""
    count = int(stats.get("count", 0))
    if count == 0:
        return {feature: 0.0 for feature in FEATURES}
    return {feature: float(stats.get(f"{feature}_mean", 0.0)) for feature in FEATURES}


def classify(
    features: dict[str, float], programs: dict[str, dict[str, Any]]
) -> tuple[str | None, float | None]:
    """Classify a cycle against known programs.

    Returns a tuple of the best matching program id and the similarity score
    in [0, 1], or (None, None) when there are no labeled programs.
    """
    candidates = {
        program_id: program
        for program_id, program in programs.items()
        if int(program.get("samples", 0)) > 0
    }
    if not candidates:
        return None, None

    # Normalization range over all program means and the current sample.
    vectors = [_means(program.get(PROG_STATS, {})) for program in candidates.values()]
    vectors.append(features)
    ranges: dict[str, float] = {}
    for feature in FEATURES:
        values = [vector[feature] for vector in vectors]
        ranges[feature] = max(values) - min(values) or _EPSILON

    weight_sum = sum(WEIGHTS.values())

    best_id: str | None = None
    best_similarity = -1.0
    for program_id, program in candidates.items():
        mean = _means(program.get(PROG_STATS, {}))
        distance = 0.0
        for feature in FEATURES:
            scaled = (features[feature] - mean[feature]) / ranges[feature]
            distance += WEIGHTS[feature] * scaled * scaled
        distance = math.sqrt(distance / weight_sum)
        similarity = max(0.0, 1.0 - distance)
        if similarity > best_similarity:
            best_similarity = similarity
            best_id = program_id

    return best_id, best_similarity
