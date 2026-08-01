"""Entities exposed by the ApplianceVibration integration.

Every appliance device gets a set of entities describing its current cycle:

- `cycle` (binary_sensor): on while a vibration cycle is running
- `stage` (sensor, enum): the current stage (wash, rinse, spin, ...)
- `stage_duration` (sensor): how long the current stage has lasted
- `time_remaining` (sensor): estimated time left in the running cycle
- `program` (sensor, enum): detected or manually labeled program
- `level` (sensor): current vibration magnitude
- `duration` (sensor): elapsed or last cycle duration
- `count` (sensor): number of completed cycles
"""

from __future__ import annotations

import time
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity, EntityCategory

from . import stages
from .const import (
    DOMAIN,
    KEY_COUNT,
    KEY_CYCLE,
    KEY_DURATION,
    KEY_LEVEL,
    KEY_PROGRAM,
    KEY_STAGE,
    KEY_STAGE_DURATION,
    KEY_TIME_REMAINING,
    UNCLASSIFIED,
)

_MANUFACTURER = "ApplianceVibration"
_MODEL = "Vibration Monitor"


class ApplianceVibrationEntity(Entity):
    """Base entity tied to an appliance device."""

    PLATFORM = "sensor"

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: Any, device_id: str, key: str) -> None:
        """Initialize the entity."""
        self._manager = manager
        self._device_id = device_id
        self._key = key
        self._attr_unique_id = f"{device_id}-{key}"
        self._attr_translation_key = key
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer=_MANUFACTURER,
            model=_MODEL,
            sw_version=manager.version or None,
        )

    @property
    def _device(self) -> dict[str, Any]:
        """Return the stored device data."""
        return self._manager.devices[self._device_id]

    @property
    def _monitor(self) -> Any:
        """Return the device monitor."""
        return self._manager.monitors[self._device_id]

    def _push(self) -> None:
        """Publish the current state to Home Assistant."""
        self.async_write_ha_state()


class VibrationCycleEntity(ApplianceVibrationEntity, BinarySensorEntity):
    """Binary sensor indicating whether a cycle is currently running."""

    PLATFORM = "binary_sensor"

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, manager: Any, device_id: str) -> None:
        """Initialize the entity."""
        super().__init__(manager, device_id, KEY_CYCLE)

    @property
    def is_on(self) -> bool:
        """Return whether a cycle is running."""
        return self._monitor.running

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return state attributes."""
        monitor = self._monitor
        return {
            "magnitude": monitor.magnitude,
            "stage": monitor.stage,
            "time_remaining": (
                round(monitor.time_remaining / 60.0, 2)
                if monitor.time_remaining is not None
                else None
            ),
            "progress": monitor.progress,
        }


class VibrationStageEntity(ApplianceVibrationEntity, SensorEntity):
    """Enum sensor with the current stage of the running cycle."""

    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, manager: Any, device_id: str) -> None:
        """Initialize the entity."""
        super().__init__(manager, device_id, KEY_STAGE)
        self._options = [stages.STAGE_IDLE, *stages.STAGE_IDS]

    @property
    def options(self) -> list[str]:
        """Return the possible stage ids."""
        return self._options

    @property
    def native_value(self) -> str:
        """Return the current stage id."""
        return self._monitor.stage or stages.STAGE_IDLE

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return state attributes."""
        return {"since": self._monitor.stage_started_at}


class VibrationStageDurationEntity(ApplianceVibrationEntity, SensorEntity):
    """Sensor with the elapsed time in the current stage."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager: Any, device_id: str) -> None:
        """Initialize the entity."""
        super().__init__(manager, device_id, KEY_STAGE_DURATION)

    @property
    def native_value(self) -> float:
        """Return the stage duration in minutes."""
        monitor = self._monitor
        if monitor.running and monitor.stage_started_at:
            return round((time.time() - monitor.stage_started_at) / 60.0, 2)
        return 0.0


class VibrationTimeRemainingEntity(ApplianceVibrationEntity, SensorEntity):
    """Sensor with the estimated time remaining in the running cycle."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager: Any, device_id: str) -> None:
        """Initialize the entity."""
        super().__init__(manager, device_id, KEY_TIME_REMAINING)

    @property
    def native_value(self) -> float:
        """Return the time remaining in minutes."""
        monitor = self._monitor
        if monitor.running and monitor.time_remaining is not None:
            return round(monitor.time_remaining / 60.0, 2)
        return 0.0

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return state attributes."""
        monitor = self._monitor
        return {
            "expected_total": (
                round(monitor.expected_total / 60.0, 2)
                if monitor.expected_total is not None
                else None
            ),
            "progress": monitor.progress,
        }


class VibrationProgramEntity(ApplianceVibrationEntity, SensorEntity):
    """Enum sensor with the detected (or labeled) program."""

    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, manager: Any, device_id: str) -> None:
        """Initialize the entity."""
        super().__init__(manager, device_id, KEY_PROGRAM)
        self._options = [UNCLASSIFIED]

    @property
    def options(self) -> list[str]:
        """Return the possible program names."""
        return self._options

    @property
    def native_value(self) -> str:
        """Return the current program."""
        program_id = self._monitor.program_id
        if program_id:
            program = self._device.get("programs", {}).get(program_id)
            if program:
                return str(program["name"])
        return UNCLASSIFIED

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return state attributes."""
        attrs: dict[str, Any] = {
            "program_id": self._monitor.program_id,
            "confidence": self._monitor.confidence,
        }
        return attrs

    def update_options(self) -> None:
        """Synchronize the option list with the stored programs."""
        options = [
            str(program["name"])
            for program in self._device.get("programs", {}).values()
        ]
        self._options = [UNCLASSIFIED, *options]


class VibrationLevelEntity(ApplianceVibrationEntity, SensorEntity):
    """Sensor with the current vibration magnitude."""

    _attr_native_unit_of_measurement = "g"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager: Any, device_id: str) -> None:
        """Initialize the entity."""
        super().__init__(manager, device_id, KEY_LEVEL)

    @property
    def native_value(self) -> float:
        """Return the current magnitude."""
        return self._monitor.magnitude

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return state attributes."""
        return {axis: value for axis, value in self._monitor.axes.items()}


class VibrationDurationEntity(ApplianceVibrationEntity, SensorEntity):
    """Sensor with the elapsed or last cycle duration."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager: Any, device_id: str) -> None:
        """Initialize the entity."""
        super().__init__(manager, device_id, KEY_DURATION)

    @property
    def native_value(self) -> float:
        """Return the current duration in minutes."""
        if self._monitor.running and self._monitor.since:
            return round((time.time() - self._monitor.since) / 60.0, 2)
        return self._monitor.last_duration


class VibrationCountEntity(ApplianceVibrationEntity, SensorEntity):
    """Diagnostic sensor counting the completed cycles."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, manager: Any, device_id: str) -> None:
        """Initialize the entity."""
        super().__init__(manager, device_id, KEY_COUNT)

    @property
    def native_value(self) -> int:
        """Return the number of completed cycles."""
        return len(self._device.get("cycles", []))


# Maps entity keys to their classes so entities can be created per key.
ENTITY_CLASSES: dict[str, type[ApplianceVibrationEntity]] = {
    KEY_CYCLE: VibrationCycleEntity,
    KEY_PROGRAM: VibrationProgramEntity,
    KEY_LEVEL: VibrationLevelEntity,
    KEY_DURATION: VibrationDurationEntity,
    KEY_COUNT: VibrationCountEntity,
    KEY_STAGE: VibrationStageEntity,
    KEY_STAGE_DURATION: VibrationStageDurationEntity,
    KEY_TIME_REMAINING: VibrationTimeRemainingEntity,
}
