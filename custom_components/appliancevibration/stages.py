"""Appliance stage patterns for the ApplianceVibration integration.

While a cycle runs, the vibration level is mapped to activity bands and used
to detect the current stage (wash, rinse, spin, ...). The stages seen so far
are matched against common stage sequences (patterns) such as

    wash -> drain -> rinse -> drain -> spin

to estimate how long the whole cycle will take and how much time remains.
"""

from __future__ import annotations

from typing import Any

# Activity level bands. Magnitude thresholds are relative to the device
# threshold; binary-only devices use the rolling activity ratio instead.
LEVEL_IDLE = "idle"
LEVEL_LOW = "low"
LEVEL_MEDIUM = "medium"
LEVEL_HIGH = "high"

# Stage ids (also used as enum sensor states).
STAGE_SOAK = "soak"
STAGE_WASH = "wash"
STAGE_RINSE = "rinse"
STAGE_DRAIN = "drain"
STAGE_SPIN = "spin"
STAGE_PAUSE = "pause"
STAGE_IDLE = "idle"

# A level band must persist this long before the stage switches.
STAGE_HOLD_SECONDS = 12
# A pause inside a cycle becomes a soak after this many seconds.
SOAK_AFTER_SECONDS = 120
# Fallback expected cycle length while no program or template is known yet.
DEFAULT_CYCLE_SECONDS = 3600.0

STAGES: dict[str, dict[str, Any]] = {
    STAGE_SOAK: {
        "label": "Soak",
        "color": "#8e24aa",
        "level": LEVEL_IDLE,
        "min_s": 60.0,
        "max_s": 3600.0,
        "default_s": 900.0,
    },
    STAGE_WASH: {
        "label": "Wash",
        "color": "#1e88e5",
        "level": LEVEL_MEDIUM,
        "min_s": 120.0,
        "max_s": 3600.0,
        "default_s": 1500.0,
    },
    STAGE_RINSE: {
        "label": "Rinse",
        "color": "#00897b",
        "level": LEVEL_MEDIUM,
        "min_s": 60.0,
        "max_s": 1800.0,
        "default_s": 600.0,
    },
    STAGE_DRAIN: {
        "label": "Drain",
        "color": "#757575",
        "level": LEVEL_LOW,
        "min_s": 10.0,
        "max_s": 300.0,
        "default_s": 120.0,
    },
    STAGE_SPIN: {
        "label": "Spin",
        "color": "#f4511e",
        "level": LEVEL_HIGH,
        "min_s": 30.0,
        "max_s": 1200.0,
        "default_s": 480.0,
    },
    STAGE_PAUSE: {
        "label": "Pause",
        "color": "#9e9e9e",
        "level": LEVEL_IDLE,
        "min_s": 5.0,
        "max_s": 600.0,
        "default_s": 60.0,
    },
}

STAGE_IDS = list(STAGES)

# Common stage sequences; the template with the longest matching prefix is
# used to estimate the expected cycle duration while it runs.
STAGE_TEMPLATES: list[list[str]] = [
    [STAGE_WASH, STAGE_DRAIN, STAGE_RINSE, STAGE_DRAIN, STAGE_SPIN],
    [STAGE_SOAK, STAGE_WASH, STAGE_DRAIN, STAGE_RINSE, STAGE_DRAIN, STAGE_SPIN],
    [STAGE_WASH, STAGE_DRAIN, STAGE_SPIN],
    [STAGE_RINSE, STAGE_DRAIN, STAGE_SPIN],
]


def level_for_magnitude(magnitude: float, threshold: float) -> str:
    """Classify a magnitude sample into an activity level band."""
    if threshold <= 0:
        return LEVEL_IDLE
    ratio = magnitude / threshold
    if ratio >= 3.0:
        return LEVEL_HIGH
    if ratio >= 1.5:
        return LEVEL_MEDIUM
    if magnitude > threshold:
        return LEVEL_LOW
    return LEVEL_IDLE


def level_for_activity_ratio(ratio: float) -> str:
    """Classify the rolling activity ratio of a binary sensor."""
    if ratio >= 0.9:
        return LEVEL_HIGH
    if ratio >= 0.45:
        return LEVEL_MEDIUM
    if ratio > 0.0:
        return LEVEL_LOW
    return LEVEL_IDLE


def stage_for_level(level: str, wash_seen: bool) -> tuple[str, bool]:
    """Map an activity level to a stage id, tracking wash/rinse order."""
    if level == LEVEL_HIGH:
        return STAGE_SPIN, wash_seen
    if level == LEVEL_MEDIUM:
        if wash_seen:
            return STAGE_RINSE, True
        return STAGE_WASH, True
    if level == LEVEL_LOW:
        return STAGE_DRAIN, wash_seen
    return STAGE_PAUSE, wash_seen


def match_template(stages: list[str]) -> list[str] | None:
    """Return the template whose prefix matches the stages seen so far."""
    if not stages:
        return None
    best: list[str] | None = None
    for template in STAGE_TEMPLATES:
        if len(template) < len(stages):
            continue
        if template[: len(stages)] == stages and (
            best is None or len(template) > len(best)
        ):
            best = template
    return best


def expected_stage_seconds(
    stage_id: str, stage_means: dict[str, float] | None = None
) -> float:
    """Return the expected duration of a stage in seconds.

    Uses the learned mean duration of the stage when available, otherwise the
    typical duration from the stage definition.
    """
    if stage_means and stage_id in stage_means and stage_means[stage_id] > 0:
        return stage_means[stage_id]
    stage = STAGES.get(stage_id)
    if stage is None:
        return 0.0
    return float(stage["default_s"])


def template_expected_seconds(
    template: list[str], stage_means: dict[str, float] | None = None
) -> float:
    """Return the expected total duration of a template in seconds."""
    return sum(expected_stage_seconds(stage_id, stage_means) for stage_id in template)
