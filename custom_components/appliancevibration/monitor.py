"""Per-device cycle monitoring for the ApplianceVibration integration.

A device monitor watches the assigned vibration binary sensor and the optional
X/Y/Z movement sensors. A cycle starts when vibration is sustained for
`start_delay` seconds and ends after `end_delay` seconds of silence. While a
cycle runs, the vibration level is mapped to common stages (wash, rinse, spin,
...), the stage sequence is matched against known patterns, and the estimated
time remaining is published live. When a cycle completes, its feature vector
is classified against the known programs and the result is persisted.
"""

from __future__ import annotations

import logging
import math
import time
from collections import deque
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from . import classification, stages
from .const import (
    CYC_ACTIVE_RATIO,
    CYC_CONFIDENCE,
    CYC_DURATION,
    CYC_ENDED,
    CYC_ID,
    CYC_LABELED,
    CYC_MAG_MAX,
    CYC_MAG_MEAN,
    CYC_MAG_STD,
    CYC_PROGRAM_ID,
    CYC_STAGES,
    CYC_STARTED,
    DEFAULT_END_DELAY,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MIN_DURATION,
    DEFAULT_START_DELAY,
    DEFAULT_THRESHOLD,
    DEV_CYCLES,
    DEV_ENTITIES,
    DEV_PROGRAMS,
    DEV_SETTINGS,
    MAX_CYCLES,
    PROG_STATS,
    SETTING_END_DELAY,
    SETTING_MIN_CONFIDENCE,
    SETTING_MIN_DURATION,
    SETTING_START_DELAY,
    SETTING_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)

_BINARY_ON = {"on", "home", "true", "1", "yes"}

# Rolling activity window (seconds) used to classify binary-only devices.
_BINARY_WINDOW = 90.0

# Rolling window (seconds) per axis used to estimate the gravity baseline.
_AXIS_WINDOW_SECONDS = 10.0


class DeviceMonitor:
    """Detect and classify vibration cycles for a single device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        device_data: dict[str, Any],
        update_callback: Callable[[], None],
        cycle_callback: Callable[[str, dict[str, Any]], None],
    ) -> None:
        """Initialize the monitor."""
        self.hass = hass
        self.device_id = device_id
        self.data = device_data
        self._update_callback = update_callback
        self._cycle_callback = cycle_callback

        self.running = False
        self.since: float | None = None
        self.magnitude = 0.0
        self.axes: dict[str, float | None] = {"x": None, "y": None, "z": None}
        self._vibration_seen = False

        # Live stage state.
        self.stage: str | None = None
        self.stage_started_at: float | None = None
        self.time_remaining: float | None = None
        self.expected_total: float | None = None
        self.progress: float | None = None
        self._level: str | None = None
        self._pending_level: str | None = None
        self._pending_since: float | None = None
        self._wash_seen = False
        self._cycle_start_mono: float | None = None
        self._stages: list[dict[str, Any]] = []
        self._window: deque[tuple[float, bool]] = deque(maxlen=512)
        # Raw-axis rolling windows (gravity baseline), filtered magnitude
        # history and the measured noise floor for adaptive intensity bands.
        self._axis_windows: dict[str, deque[tuple[float, float]]] = {
            axis: deque(maxlen=256) for axis in ("x", "y", "z")
        }
        self._mag_window: deque[tuple[float, float]] = deque(maxlen=512)
        self._noise_ema = 0.0

        self._start_unsub: Callable[[], None] | None = None
        self._end_unsub: Callable[[], None] | None = None
        self._last_active: float | None = None

        # Statistics accumulated while a cycle is running.
        self._samples = 0
        self._active_samples = 0
        self._sum = 0.0
        self._sum_sq = 0.0
        self._max = 0.0
        self.program_id: str | None = None
        self.confidence: float | None = None
        self.last_duration = 0.0

    @property
    def threshold(self) -> float:
        """Return the configured activity threshold."""
        return float(
            self.data.get(DEV_SETTINGS, {}).get(SETTING_THRESHOLD, DEFAULT_THRESHOLD)
        )

    @property
    def start_delay(self) -> int:
        """Return the configured cycle start delay in seconds."""
        return int(
            self.data.get(DEV_SETTINGS, {}).get(
                SETTING_START_DELAY, DEFAULT_START_DELAY
            )
        )

    @property
    def end_delay(self) -> int:
        """Return the configured cycle end delay in seconds."""
        return int(
            self.data.get(DEV_SETTINGS, {}).get(SETTING_END_DELAY, DEFAULT_END_DELAY)
        )

    @property
    def min_duration(self) -> int:
        """Return the minimum cycle duration in seconds."""
        return int(
            self.data.get(DEV_SETTINGS, {}).get(
                SETTING_MIN_DURATION, DEFAULT_MIN_DURATION
            )
        )

    async def async_shutdown(self) -> None:
        """Cancel pending timers."""
        if self._start_unsub:
            self._start_unsub()
            self._start_unsub = None
        if self._end_unsub:
            self._end_unsub()
            self._end_unsub = None

    # -- state changes -----------------------------------------------------

    def async_handle_state_change(self, event: Event) -> None:
        """Handle a state change of one of the assigned entities."""
        entity_id = event.data.get("entity_id")
        state = event.data.get("new_state")
        entities = self.data.get(DEV_ENTITIES, {})
        if entity_id not in entities.values():
            return

        self._record_sample(state)

        active = self._is_active(state, entities)
        if self.running:
            if active:
                self._last_active = time.monotonic()
                self._cancel_end_timer()
            else:
                self._schedule_end()
            self._update_callback()
            return

        if active:
            if self._start_unsub:
                return
            if self.start_delay <= 0:
                self._start_cycle()
            else:
                self._start_unsub = async_track_point_in_utc_time(
                    self.hass,
                    self._on_start_timer,
                    event.time_fired + timedelta(seconds=self.start_delay),
                )
        elif self._start_unsub:
            # Vibration stopped before the start delay elapsed.
            self._start_unsub()
            self._start_unsub = None
        self._update_callback()

    @callback
    def _on_start_timer(self, _: Any) -> None:
        """Start the cycle when the start delay elapses."""
        self._start_cycle()

    @callback
    def _on_end_timer(self, _: Any) -> None:
        """End the cycle when the end delay elapses."""
        self._end_cycle()

    # -- cycle lifecycle ---------------------------------------------------

    def _start_cycle(self) -> None:
        """Start a new cycle."""
        self._start_unsub = None
        if self.running:
            return
        self.running = True
        self.since = time.time()
        self._last_active = time.monotonic()
        self._samples = 0
        self._active_samples = 0
        self._sum = 0.0
        self._sum_sq = 0.0
        self._max = 0.0
        self._cycle_start_mono = time.monotonic()
        self._window.clear()
        self._mag_window.clear()
        self._vibration_seen = False
        self.stage = None
        self.stage_started_at = None
        self._level = None
        self._pending_level = None
        self._pending_since = None
        self._wash_seen = False
        self._stages = []
        self._estimate_remaining()
        self._schedule_end()
        _LOGGER.debug("Cycle started for %s", self.device_id)
        self._update_callback()

    def _end_cycle(self) -> None:
        """Finish the current cycle, classify it and store it."""
        self._end_unsub = None
        if not self.running:
            return
        self.running = False
        ended = time.time()
        if self._stages and self._cycle_start_mono is not None:
            self._stages[-1]["end"] = round(
                time.monotonic() - self._cycle_start_mono, 1
            )
        self.stage = None
        self.stage_started_at = None
        self.time_remaining = None
        self.expected_total = None
        self.progress = None
        self._level = None
        self._pending_level = None
        self._pending_since = None
        duration_min = (ended - (self.since or ended)) / 60.0
        entities = self.data.get(DEV_ENTITIES, {})
        if not self._vibration_seen and entities.get("vibration"):
            # The binary sensor never reported vibration during the run;
            # XYZ movements alone do not count as a cycle.
            _LOGGER.debug(
                "Cycle discarded for %s: no vibration detected (%.1fmin)",
                self.device_id,
                duration_min,
            )
            self._update_callback()
            return
        if duration_min * 60.0 < self.min_duration:
            _LOGGER.debug(
                "Cycle discarded for %s: too short (%.1fmin < %ds)",
                self.device_id,
                duration_min,
                self.min_duration,
            )
            self._update_callback()
            return
        samples = max(self._active_samples, 1)
        mean = self._sum / samples
        variance = max(0.0, self._sum_sq / samples - mean * mean)
        features = {
            CYC_DURATION: round(duration_min, 2),
            CYC_MAG_MEAN: round(mean, 4),
            CYC_MAG_MAX: round(self._max, 4),
            CYC_MAG_STD: round(math.sqrt(variance), 4),
            CYC_ACTIVE_RATIO: round(self._active_samples / max(self._samples, 1), 3),
        }

        program_id, confidence = classification.classify(
            {
                key: features[key]
                for key in (
                    CYC_DURATION,
                    CYC_MAG_MEAN,
                    CYC_MAG_MAX,
                    CYC_MAG_STD,
                )
            },
            self.data.get(DEV_PROGRAMS, {}),
        )
        min_confidence = float(
            self.data.get(DEV_SETTINGS, {}).get(
                SETTING_MIN_CONFIDENCE, DEFAULT_MIN_CONFIDENCE
            )
        )
        if program_id and confidence is not None and confidence < min_confidence:
            program_id = None
            confidence = None

        cycle = {
            CYC_ID: f"{int(ended * 1000):x}",
            CYC_STARTED: time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.gmtime(self.since or ended)
            ),
            CYC_ENDED: time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ended)),
            **features,
            CYC_PROGRAM_ID: program_id,
            CYC_CONFIDENCE: round(confidence, 3) if confidence is not None else None,
            CYC_LABELED: False,
            CYC_STAGES: self._stages,
        }
        cycles = self.data.setdefault(DEV_CYCLES, [])
        cycles.append(cycle)
        del cycles[:-MAX_CYCLES]

        self.program_id = program_id
        self.confidence = confidence
        self.last_duration = duration_min
        _LOGGER.debug(
            "Cycle ended for %s: duration=%.1fmin program=%s confidence=%s",
            self.device_id,
            duration_min,
            program_id,
            confidence,
        )
        self._cycle_callback(self.device_id, cycle)
        self._update_callback()

    # -- helpers -----------------------------------------------------------

    def _binary_active(self, entities: dict[str, str]) -> bool:
        """Return whether the assigned vibration binary sensor is on."""
        vibration_id = entities.get("vibration")
        if not vibration_id:
            return False
        vibration_state = self.hass.states.get(vibration_id)
        return vibration_state is not None and vibration_state.state in _BINARY_ON

    def _is_active(self, state: Any, entities: dict[str, str]) -> bool:
        """Return whether the device is currently vibrating.

        The vibration binary sensor decides IF the device is vibrating; the
        X/Y/Z movement sensors only describe HOW strongly. The magnitude
        fallback only applies when no binary sensor is assigned.
        """
        vibration_id = entities.get("vibration")
        if vibration_id:
            return self._binary_active(entities)

        if not (entities.get("x") or entities.get("y") or entities.get("z")):
            return False
        return self.magnitude > self.threshold

    def _record_sample(self, state: Any) -> None:
        """Update axis baselines and compute the filtered vibration magnitude.

        Raw accelerometer output (counts or milli-g) includes a constant
        gravity offset and sensor noise. The magnitude is therefore computed
        as the RMS deviation of each axis from its recent rolling mean, which
        removes the offset and leaves only the vibration intensity.
        """
        entities = self.data.get(DEV_ENTITIES, {})
        now = time.monotonic()
        for axis in ("x", "y", "z"):
            entity_id = entities.get(axis)
            value = None
            if entity_id:
                axis_state = self.hass.states.get(entity_id)
                if axis_state is not None:
                    try:
                        value = float(axis_state.state)
                    except (TypeError, ValueError):
                        value = None
            if value is not None:
                self._axis_windows[axis].append((now, value))
                self.axes[axis] = value

        magnitudes: list[float] = []
        for axis in ("x", "y", "z"):
            window = self._axis_windows[axis]
            while window and window[0][0] < now - _AXIS_WINDOW_SECONDS:
                window.popleft()
            values = [value for _, value in window]
            if not values:
                continue
            mean = sum(values) / len(values)
            variance = sum((value - mean) ** 2 for value in values) / len(values)
            magnitudes.append(variance)
        if magnitudes:
            magnitude = math.sqrt(sum(magnitudes))
        elif state is not None and state.state in _BINARY_ON:
            magnitude = 1.0
        else:
            magnitude = 0.0
        self.magnitude = round(magnitude, 4)

        active = self._is_active(state, entities)
        if self._binary_active(entities):
            self._vibration_seen = True
        self._window.append((now, active))
        self._mag_window.append((now, self.magnitude))
        self._samples += 1
        if not active and self._has_axes():
            self._noise_ema = self._noise_ema * 0.95 + self.magnitude * 0.05
        if active:
            self._active_samples += 1
            self._sum += self.magnitude
            self._sum_sq += self.magnitude * self.magnitude
            self._max = max(self._max, self.magnitude)

        if self.running:
            self._update_stage(now)

    # -- stage detection --------------------------------------------------

    def _has_axes(self) -> bool:
        """Return whether the device has assigned X/Y/Z movement sensors."""
        entities = self.data.get(DEV_ENTITIES, {})
        return bool(entities.get("x") or entities.get("y") or entities.get("z"))

    def _activity_ratio(self) -> float:
        """Return the fraction of active time over the rolling window."""
        now = time.monotonic()
        cutoff = now - _BINARY_WINDOW
        while self._window and self._window[0][0] < cutoff:
            self._window.popleft()
        if not self._window:
            return 0.0
        first = self._window[0]
        if len(self._window) == 1:
            return 1.0 if first[1] else 0.0
        total = now - first[0]
        if total <= 0:
            return 1.0 if first[1] else 0.0
        active_time = 0.0
        prev_time, prev_active = first
        for sample_time, is_active in self._window:
            if prev_active:
                active_time += sample_time - prev_time
            prev_time, prev_active = sample_time, is_active
        if prev_active:
            active_time += now - prev_time
        return min(1.0, max(0.0, active_time / total))

    def _recent_mag_max(self, window_seconds: float = 60.0) -> float:
        """Return the peak filtered magnitude over the recent window."""
        cutoff = time.monotonic() - window_seconds
        best = 0.0
        for sample_time, magnitude in self._mag_window:
            if sample_time >= cutoff:
                best = max(best, magnitude)
        return best

    def _level_band(self) -> str:
        """Classify the current sample into an activity level band."""
        if self._has_axes():
            if len(self._mag_window) < 5:
                return stages.LEVEL_IDLE
            return stages.level_for_intensity(
                self.magnitude, self._noise_ema, self._recent_mag_max()
            )
        return stages.level_for_activity_ratio(self._activity_ratio())

    def _update_stage(self, now: float) -> None:
        """Track the activity level and switch stages when it settles."""
        level = self._level_band()
        if level == self._level:
            self._pending_level = None
        elif self._pending_level == level and self._pending_since is not None:
            if now - self._pending_since >= stages.STAGE_HOLD_SECONDS:
                self._begin_stage(level, now)
        else:
            self._pending_level = level
            self._pending_since = now

        if (
            self.stage == stages.STAGE_PAUSE
            and self.stage_started_at is not None
            and time.time() - self.stage_started_at >= stages.SOAK_AFTER_SECONDS
        ):
            self.stage = stages.STAGE_SOAK
            if self._stages:
                self._stages[-1]["id"] = stages.STAGE_SOAK
            self._estimate_remaining()
            self._update_callback()

    def _begin_stage(self, level: str, now: float) -> None:
        """Start a new stage for the settled activity level."""
        elapsed = (
            (now - self._cycle_start_mono)
            if self._cycle_start_mono is not None
            else 0.0
        )
        if self._stages:
            self._stages[-1]["end"] = round(elapsed, 1)
        stage_id, wash_seen = stages.stage_for_level(level, self._wash_seen)
        self._wash_seen = wash_seen
        self._level = level
        self._pending_level = None
        self._pending_since = None
        self.stage = stage_id
        self.stage_started_at = time.time()
        self._stages.append({"id": stage_id, "start": round(elapsed, 1), "end": None})
        self._estimate_remaining()
        _LOGGER.debug("Stage %s for %s", stage_id, self.device_id)
        self._update_callback()

    def _stage_means(self) -> dict[str, float]:
        """Return the learned mean duration of each stage in seconds."""
        means: dict[str, float] = {}
        counts: dict[str, int] = {}
        for cycle in self.data.get(DEV_CYCLES, []):
            if not cycle.get(CYC_PROGRAM_ID):
                continue
            for stage in cycle.get(CYC_STAGES, []):
                start = stage.get("start")
                end = stage.get("end")
                if start is None or end is None:
                    continue
                duration = float(end) - float(start)
                if duration <= 0:
                    continue
                stage_id = stage.get("id")
                means[stage_id] = means.get(stage_id, 0.0) + duration
                counts[stage_id] = counts.get(stage_id, 0) + 1
        return {
            stage_id: means[stage_id] / counts[stage_id]
            for stage_id in means
            if counts.get(stage_id, 0) > 0
        }

    def _expected_total(self) -> float:
        """Estimate the expected total duration of the current cycle."""
        programs = self.data.get(DEV_PROGRAMS, {})
        if self.program_id and self.program_id in programs:
            stats = programs[self.program_id].get(PROG_STATS, {})
            if int(stats.get("count", 0)) > 0:
                mean = float(stats.get(f"{CYC_DURATION}_mean", 0.0) or 0.0)
                if mean > 0:
                    return mean * 60.0
        sequence = [stage["id"] for stage in self._stages]
        template = stages.match_template(sequence) if sequence else None
        if template:
            return stages.template_expected_seconds(template, self._stage_means())
        return stages.DEFAULT_CYCLE_SECONDS

    def _estimate_remaining(self) -> None:
        """Refresh the expected total and the time remaining."""
        expected = self._expected_total()
        self.expected_total = expected
        if not self.running or not self.since:
            self.time_remaining = None
            self.progress = None
            return
        elapsed = time.time() - self.since
        self.time_remaining = max(0.0, expected - elapsed)
        self.progress = min(1.0, max(0.0, elapsed / expected)) if expected > 0 else None

    def _schedule_end(self) -> None:
        """Schedule the end-of-cycle check."""
        if self._end_unsub:
            return
        self._end_unsub = async_track_point_in_utc_time(
            self.hass,
            self._on_end_timer,
            dt_util.utcnow() + timedelta(seconds=self.end_delay),
        )

    def _cancel_end_timer(self) -> None:
        """Cancel a pending end-of-cycle check."""
        if self._end_unsub:
            self._end_unsub()
            self._end_unsub = None

    # -- snapshot ----------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return the live state of the monitor."""
        stage_duration = 0.0
        if self.running and self.stage_started_at is not None:
            stage_duration = max(0.0, time.time() - self.stage_started_at)
        return {
            "running": self.running,
            "since": self.since,
            "magnitude": self.magnitude,
            "axes": self.axes,
            "program_id": self.program_id,
            "confidence": self.confidence,
            "stage": self.stage,
            "stage_started_at": self.stage_started_at,
            "stage_duration": round(stage_duration, 1),
            "level": self._level,
            "time_remaining": (
                round(self.time_remaining, 1)
                if self.time_remaining is not None
                else None
            ),
            "expected_total": (
                round(self.expected_total, 1)
                if self.expected_total is not None
                else None
            ),
            "progress": (
                round(self.progress, 3) if self.progress is not None else None
            ),
            "stages": self._stages,
        }
