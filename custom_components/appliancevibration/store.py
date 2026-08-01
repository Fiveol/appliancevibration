"""Storage for the ApplianceVibration integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import ATTR_DEVICES, STORAGE_KEY, STORAGE_VERSION

_MIGRATION_VERSION = 1


class ApplianceVibrationStore:
    """Class to persist appliance device data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self._store: Store[dict] = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
            atomic_writes=True,
            minor_version=_MIGRATION_VERSION,
        )

    async def async_load(self) -> dict[str, dict]:
        """Load the stored device data."""
        data = await self._store.async_load()
        if data is None:
            return {}
        return data.get(ATTR_DEVICES, {})

    async def async_save(self, devices: dict[str, dict]) -> None:
        """Persist the device data."""
        await self._store.async_save({ATTR_DEVICES: devices})
