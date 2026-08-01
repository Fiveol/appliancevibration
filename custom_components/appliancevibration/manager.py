"""Device manager for the ApplianceVibration integration.

Owns the persisted device data, the Home Assistant device/entity registry
entries, and the per-device cycle monitors.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from homeassistant.core import EVENT_STATE_CHANGED, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity, slugify

from . import classification
from .const import (
    CYC_CONFIDENCE,
    CYC_ID,
    CYC_LABELED,
    CYC_PROGRAM_ID,
    CYC_STAGES,
    DEV_CYCLES,
    DEV_ENT_IDS,
    DEV_ENTITIES,
    DEV_ID,
    DEV_NAME,
    DEV_PROGRAMS,
    DEV_SETTINGS,
    DEV_SLUG,
    DOMAIN,
    ENTITY_KEYS,
    PROG_COLOR,
    PROG_NAME,
    PROG_SAMPLES,
    PROGRAM_COLORS,
    SETTING_END_DELAY,
    SETTING_MIN_CONFIDENCE,
    SETTING_START_DELAY,
    SETTING_THRESHOLD,
)
from .entities import ENTITY_CLASSES, VibrationProgramEntity
from .monitor import DeviceMonitor
from .store import ApplianceVibrationStore

_LOGGER = logging.getLogger(__name__)

# Read once at module load; with `import_executor` in the manifest this runs
# in the executor, so it never blocks the event loop.
_MANIFEST_VERSION: str = json.loads(
    (Path(__file__).parent / "manifest.json").read_text()
)["version"]


class ApplianceVibrationManager:
    """Manage appliance devices, entities and monitors."""

    def __init__(self, hass: HomeAssistant, entry: Any) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.entry = entry
        self.version = _MANIFEST_VERSION
        self.store = ApplianceVibrationStore(hass)
        self.devices: dict[str, dict[str, Any]] = {}
        self.monitors: dict[str, DeviceMonitor] = {}
        self._adders: dict[str, list[Callable[[list[Entity]], None]]] = {
            "sensor": [],
            "binary_sensor": [],
        }
        self._unsub_state: Callable[[], None] | None = None
        self._entity_map: dict[str, list[Entity]] = {}

    # -- setup -------------------------------------------------------------

    async def async_setup(self) -> None:
        """Load stored data and create monitors for existing devices."""
        devices = await self.store.async_load()
        for data in devices.values():
            self._normalize_device(data)
        self.devices = devices
        for device_id, data in devices.items():
            self.monitors[device_id] = self._create_monitor(device_id, data)
        self._unsub_state = self.hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._async_state_changed
        )

    @callback
    def async_start(self) -> None:
        """Create device registry entries and entities for all devices."""
        for device_id in self.devices:
            self._ensure_device_registry(self.devices[device_id])
            self.hass.async_create_background_task(
                self._ensure_entities(device_id),
                f"appliancevibration_ensure_entities_{device_id}",
            )

    async def async_shutdown(self) -> None:
        """Shut down all monitors."""
        if self._unsub_state:
            self._unsub_state()
            self._unsub_state = None
        for monitor in self.monitors.values():
            await monitor.async_shutdown()

    # -- entity platform hookup --------------------------------------------

    @callback
    def register_adder(
        self, platform: str, adder: Callable[[list[Entity]], None]
    ) -> None:
        """Register an entity adder for a platform."""
        self._adders[platform].append(adder)

    async def _add_entities(self, entities: list[Entity]) -> None:
        """Add entities through the registered platform adders.

        The platform adders are scheduling callbacks (they return None and add
        the entities in an eager background task), so we wait until the entity
        platforms have processed the entities before returning.
        """
        for entity in entities:
            for adder in self._adders[entity.PLATFORM]:
                adder([entity])
        deadline = time.monotonic() + 5.0
        while any(entity.entity_id is None for entity in entities):
            if time.monotonic() >= deadline:
                device_id = entities[0]._device_id if entities else "?"
                _LOGGER.warning(
                    "Timed out waiting for the entities of device %s to be added",
                    device_id,
                )
                break
            await asyncio.sleep(0)

    # -- device registry ---------------------------------------------------

    def _ensure_device_registry(self, data: dict[str, Any]) -> dr.DeviceEntry:
        """Create or update the Home Assistant device registry entry."""
        registry = dr.async_get(self.hass)
        return registry.async_get_or_create(
            config_entry_id=self.entry.entry_id,
            identifiers={(DOMAIN, data[DEV_ID])},
            name=data[DEV_NAME],
            manufacturer="ApplianceVibration",
            model="Vibration Monitor",
            sw_version=self.version or None,
        )

    # -- entity creation ---------------------------------------------------

    async def _ensure_entities(self, device_id: str) -> None:
        """Create the entities for a device that do not exist yet.

        Only the missing keys are created so existing devices are migrated
        when new entity types are introduced.
        """
        data = self.devices[device_id]
        existing = data.setdefault(DEV_ENT_IDS, {})
        missing = [key for key in ENTITY_KEYS if key not in existing]
        if not missing:
            self._update_program_options(device_id)
            return

        entities = [ENTITY_CLASSES[key](self, device_id) for key in missing]
        self._entity_map.setdefault(device_id, []).extend(entities)
        await self._add_entities(entities)

        for entity in entities:
            if entity.entity_id:
                existing[entity._key] = entity.entity_id
        data[DEV_ENT_IDS] = existing
        self._update_program_options(device_id)

    def _update_program_options(self, device_id: str) -> None:
        """Refresh the enum options of the program entity."""
        for entity in self._entity_map.get(device_id, []):
            if isinstance(entity, VibrationProgramEntity):
                entity.update_options()
                if entity.entity_id:
                    entity.async_write_ha_state()

    # -- monitors ----------------------------------------------------------

    def _create_monitor(self, device_id: str, data: dict[str, Any]) -> DeviceMonitor:
        """Create a monitor for a device."""
        return DeviceMonitor(
            self.hass,
            device_id,
            data,
            update_callback=lambda: self.async_push(device_id),
            cycle_callback=lambda _id, _cycle: self._on_cycle(device_id),
        )

    @callback
    def async_push(self, device_id: str) -> None:
        """Publish entity state updates for a device."""
        for entity in self._entity_map.get(device_id, []):
            entity.async_write_ha_state()

    def _on_cycle(self, device_id: str) -> None:
        """Persist after a cycle completed."""
        self.hass.async_create_task(self._save())

    @callback
    def _async_state_changed(self, event: Event) -> None:
        """Dispatch state changes to the monitors."""
        entity_id = event.data.get("entity_id")
        if not entity_id:
            return
        for monitor in self.monitors.values():
            if entity_id in monitor.data.get(DEV_ENTITIES, {}).values():
                monitor.async_handle_state_change(event)

    # -- mutations ---------------------------------------------------------

    async def async_create_device(
        self, name: str, entities: dict[str, str | None], settings: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a new appliance device."""
        name = name.strip()
        if not name:
            raise HomeAssistantError("A device name is required")
        if not entities.get("vibration"):
            raise HomeAssistantError("A vibration sensor is required")
        self._validate_entities(entities)

        device_id = uuid4().hex
        data: dict[str, Any] = {
            DEV_ID: device_id,
            DEV_NAME: name,
            DEV_SLUG: self._unique_slug(name),
            DEV_ENTITIES: entities,
            DEV_SETTINGS: self._normalize_settings(settings),
            DEV_PROGRAMS: {},
            DEV_CYCLES: [],
            DEV_ENT_IDS: {},
        }
        self._normalize_device(data)
        self.devices[device_id] = data
        self.monitors[device_id] = self._create_monitor(device_id, data)
        self._ensure_device_registry(data)
        await self._ensure_entities(device_id)
        await self._save()
        return data

    async def async_update_device(
        self,
        device_id: str,
        name: str | None = None,
        entities: dict[str, str | None] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        """Update an appliance device."""
        data = self._get_device(device_id)
        if name:
            data[DEV_NAME] = name.strip()
        if entities is not None:
            self._validate_entities(entities)
            data[DEV_ENTITIES] = entities
        if settings is not None:
            data[DEV_SETTINGS].update(self._normalize_settings(settings))
        self._ensure_device_registry(data)
        await self._save()

    async def async_remove_device(self, device_id: str) -> None:
        """Remove an appliance device including its entities."""
        data = self._get_device(device_id)

        monitor = self.monitors.pop(device_id, None)
        if monitor:
            await monitor.async_shutdown()

        registry = self.hass.helpers.entity_registry.async_get(self.hass)
        for entity_id in data.get(DEV_ENT_IDS, {}).values():
            if registry.async_get(entity_id):
                registry.async_remove(entity_id)
        self._entity_map.pop(device_id, None)

        device_registry = dr.async_get(self.hass)
        if device := device_registry.async_get_device(
            identifiers={(DOMAIN, device_id)}
        ):
            device_registry.async_remove_device(device.id)

        self.devices.pop(device_id, None)
        await self._save()

    async def async_label_cycle(
        self,
        device_id: str,
        cycle_id: str,
        program_id: str | None = None,
        new_program_name: str | None = None,
        new_program_color: str | None = None,
    ) -> None:
        """Label a cycle with a program (or unlabel it)."""
        data = self._get_device(device_id)
        cycle = next(
            (c for c in data.get(DEV_CYCLES, []) if c[CYC_ID] == cycle_id), None
        )
        if cycle is None:
            raise HomeAssistantError("Cycle not found")

        programs = data.setdefault(DEV_PROGRAMS, {})

        if new_program_name:
            program_id = self._create_program(data, new_program_name, new_program_color)

        old_program_id = cycle.get(CYC_PROGRAM_ID)
        if old_program_id and old_program_id != program_id:
            if old_program := programs.get(old_program_id):
                classification.remove_sample(old_program, cycle)

        cycle[CYC_PROGRAM_ID] = program_id
        cycle[CYC_LABELED] = program_id is not None
        cycle[CYC_CONFIDENCE] = None

        monitor = self.monitors[device_id]
        if program_id:
            classification.add_sample(programs[program_id], cycle)
            monitor.program_id = program_id
        else:
            monitor.program_id = None
        monitor.confidence = None

        self._update_program_options(device_id)
        self.async_push(device_id)
        await self._save()

    async def async_set_programs(
        self, device_id: str, programs: list[dict[str, Any]]
    ) -> None:
        """Replace the program list (adds, renames, deletes)."""
        data = self._get_device(device_id)
        existing = data.setdefault(DEV_PROGRAMS, {})
        desired_ids: set[str] = set()

        for program in programs:
            program_id = program.get("id")
            name = str(program["name"]).strip()
            if not name:
                continue
            color = str(program.get(PROG_COLOR, "") or "").strip()
            if program_id and program_id in existing:
                desired_ids.add(program_id)
                existing[program_id][PROG_NAME] = name
                if color:
                    existing[program_id][PROG_COLOR] = color
            else:
                new_id = uuid4().hex[:8]
                desired_ids.add(new_id)
                existing[new_id] = {
                    PROG_NAME: name,
                    PROG_COLOR: color
                    or PROGRAM_COLORS[len(existing) % len(PROGRAM_COLORS)],
                    PROG_SAMPLES: 0,
                    "stats": {},
                }

        for program_id in [pid for pid in existing if pid not in desired_ids]:
            del existing[program_id]

        for cycle in data.get(DEV_CYCLES, []):
            if cycle.get(CYC_PROGRAM_ID) not in existing:
                cycle[CYC_PROGRAM_ID] = None
                cycle[CYC_LABELED] = False
                cycle[CYC_CONFIDENCE] = None

        self._update_program_options(device_id)
        self.async_push(device_id)
        await self._save()

    async def async_reset_learning(self, device_id: str) -> None:
        """Clear the programs and cycles of a device."""
        data = self._get_device(device_id)
        data[DEV_PROGRAMS] = {}
        data[DEV_CYCLES] = []
        monitor = self.monitors[device_id]
        monitor.program_id = None
        monitor.confidence = None
        self._update_program_options(device_id)
        self.async_push(device_id)
        await self._save()

    async def async_reset_all(self) -> None:
        """Remove all devices and their data."""
        for device_id in list(self.devices):
            await self.async_remove_device(device_id)

    # -- helpers -----------------------------------------------------------

    def _get_device(self, device_id: str) -> dict[str, Any]:
        """Return the stored device data."""
        if device_id not in self.devices:
            raise HomeAssistantError(f"Unknown device {device_id}")
        return self.devices[device_id]

    def _normalize_device(self, data: dict[str, Any]) -> None:
        """Fill in defaults for stored device data."""
        data.setdefault(DEV_ENT_IDS, {})
        data.setdefault(DEV_PROGRAMS, {})
        data.setdefault(DEV_CYCLES, [])
        data.setdefault(DEV_SLUG, slugify(str(data.get(DEV_NAME, ""))))
        data.setdefault(DEV_SETTINGS, {})
        data[DEV_SETTINGS] = self._normalize_settings(data[DEV_SETTINGS])

    def _validate_entities(self, entities: dict[str, str | None]) -> None:
        """Validate that all assigned entities exist."""
        for key, entity_id in entities.items():
            if not entity_id:
                continue
            if self.hass.states.get(entity_id) is None:
                raise HomeAssistantError(f"Unknown entity {entity_id}")

    def _normalize_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Coerce and clamp device settings."""
        normalized = {
            SETTING_THRESHOLD: float(settings.get(SETTING_THRESHOLD, 0.2)),
            SETTING_START_DELAY: int(settings.get(SETTING_START_DELAY, 10)),
            SETTING_END_DELAY: int(settings.get(SETTING_END_DELAY, 60)),
            SETTING_MIN_CONFIDENCE: float(settings.get(SETTING_MIN_CONFIDENCE, 0.7)),
        }
        normalized[SETTING_THRESHOLD] = min(
            1.0, max(0.0, normalized[SETTING_THRESHOLD])
        )
        normalized[SETTING_START_DELAY] = min(
            300, max(0, normalized[SETTING_START_DELAY])
        )
        normalized[SETTING_END_DELAY] = min(600, max(10, normalized[SETTING_END_DELAY]))
        normalized[SETTING_MIN_CONFIDENCE] = min(
            0.99, max(0.5, normalized[SETTING_MIN_CONFIDENCE])
        )
        return normalized

    def _unique_slug(self, name: str) -> str:
        """Return a slug unique among the stored devices."""
        base = slugify(name)
        slug = base
        index = 2
        while any(data.get(DEV_SLUG) == slug for data in self.devices.values()):
            slug = f"{base}-{index}"
            index += 1
        return slug

    def _create_program(
        self, data: dict[str, Any], name: str, color: str | None
    ) -> str:
        """Create a new program for a device."""
        name = name.strip()
        if not name:
            raise HomeAssistantError("A program name is required")
        programs = data.setdefault(DEV_PROGRAMS, {})
        program_id = uuid4().hex[:8]
        programs[program_id] = {
            PROG_NAME: name,
            PROG_COLOR: color or PROGRAM_COLORS[len(programs) % len(PROGRAM_COLORS)],
            PROG_SAMPLES: 0,
            "stats": {},
        }
        return program_id

    async def _save(self) -> None:
        """Persist the device data."""
        await self.store.async_save(self.devices)

    # -- snapshot ----------------------------------------------------------

    def config_snapshot(self) -> dict[str, Any]:
        """Return the configuration for the frontend."""
        devices = []
        for device_id, data in self.devices.items():
            programs = [
                {
                    "id": program_id,
                    "name": program[PROG_NAME],
                    "color": program[PROG_COLOR],
                    "samples": program.get(PROG_SAMPLES, 0),
                }
                for program_id, program in data.get(DEV_PROGRAMS, {}).items()
            ]
            cycles = [
                {
                    "id": cycle[CYC_ID],
                    "started": cycle["started"],
                    "ended": cycle["ended"],
                    "duration": cycle["duration"],
                    "magnitude_mean": cycle["magnitude_mean"],
                    "magnitude_max": cycle["magnitude_max"],
                    "magnitude_std": cycle["magnitude_std"],
                    "active_ratio": cycle["active_ratio"],
                    "program_id": cycle.get(CYC_PROGRAM_ID),
                    "confidence": cycle.get(CYC_CONFIDENCE),
                    "labeled": cycle.get(CYC_LABELED, False),
                    "stages": cycle.get(CYC_STAGES, []),
                }
                for cycle in reversed(data.get(DEV_CYCLES, []))
            ]
            monitor = self.monitors.get(device_id)
            devices.append(
                {
                    "id": device_id,
                    "name": data[DEV_NAME],
                    "entities": data.get(DEV_ENTITIES, {}),
                    "entity_ids": data.get(DEV_ENT_IDS, {}),
                    "settings": data.get(DEV_SETTINGS, {}),
                    "programs": programs,
                    "cycles": cycles,
                    "state": monitor.snapshot() if monitor else {},
                }
            )
        return {"devices": devices}
