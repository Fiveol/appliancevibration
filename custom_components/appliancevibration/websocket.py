"""WebSocket API for the ApplianceVibration integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .manager import ApplianceVibrationManager

WS_TYPE_CONFIG = f"{DOMAIN}/config"
WS_TYPE_CREATE = f"{DOMAIN}/device/create"
WS_TYPE_UPDATE = f"{DOMAIN}/device/update"
WS_TYPE_REMOVE = f"{DOMAIN}/device/remove"
WS_TYPE_LABEL = f"{DOMAIN}/device/label_cycle"
WS_TYPE_PROGRAMS = f"{DOMAIN}/device/programs"
WS_TYPE_RESET_LEARNING = f"{DOMAIN}/device/reset_learning"
WS_TYPE_RESET_ALL = f"{DOMAIN}/reset_all"

_ENTITY_SCHEMA = {
    vol.Required("vibration"): vol.Any(cv.entity_id, None),
    vol.Optional("x", default=None): vol.Any(cv.entity_id, None),
    vol.Optional("y", default=None): vol.Any(cv.entity_id, None),
    vol.Optional("z", default=None): vol.Any(cv.entity_id, None),
}

_SETTINGS_SCHEMA = {
    vol.Optional("threshold", default=0.2): vol.Coerce(float),
    vol.Optional("start_delay", default=10): vol.Coerce(int),
    vol.Optional("end_delay", default=60): vol.Coerce(int),
    vol.Optional("min_confidence", default=0.7): vol.Coerce(float),
    vol.Optional("min_duration", default=300): vol.Coerce(int),
}

_PROGRAM_SCHEMA = {
    vol.Optional("id"): cv.string,
    vol.Required("name"): cv.string,
    vol.Optional("color"): cv.string,
}


def async_register_websocket_commands(
    hass: HomeAssistant, manager: ApplianceVibrationManager
) -> None:
    """Register all websocket commands."""

    @websocket_api.websocket_command({vol.Required("type"): WS_TYPE_CONFIG})
    @websocket_api.require_admin
    @websocket_api.async_response
    async def handle_config(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Return the full configuration."""
        connection.send_result(msg["id"], manager.config_snapshot())

    @websocket_api.websocket_command(
        {
            vol.Required("type"): WS_TYPE_CREATE,
            vol.Required("name"): cv.string,
            vol.Required("entities"): _ENTITY_SCHEMA,
            vol.Optional("settings", default={}): _SETTINGS_SCHEMA,
        }
    )
    @websocket_api.require_admin
    @websocket_api.async_response
    async def handle_create(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Create a new appliance device."""
        device = await manager.async_create_device(
            msg["name"], msg["entities"], msg["settings"]
        )
        connection.send_result(msg["id"], {"id": device["id"]})

    @websocket_api.websocket_command(
        {
            vol.Required("type"): WS_TYPE_UPDATE,
            vol.Required("id"): cv.string,
            vol.Optional("name"): cv.string,
            vol.Optional("entities"): _ENTITY_SCHEMA,
            vol.Optional("settings"): _SETTINGS_SCHEMA,
        }
    )
    @websocket_api.require_admin
    @websocket_api.async_response
    async def handle_update(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Update an appliance device."""
        await manager.async_update_device(
            msg["id"],
            name=msg.get("name"),
            entities=msg.get("entities"),
            settings=msg.get("settings"),
        )
        connection.send_result(msg["id"])

    @websocket_api.websocket_command(
        {
            vol.Required("type"): WS_TYPE_REMOVE,
            vol.Required("id"): cv.string,
        }
    )
    @websocket_api.require_admin
    @websocket_api.async_response
    async def handle_remove(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Remove an appliance device."""
        await manager.async_remove_device(msg["id"])
        connection.send_result(msg["id"])

    @websocket_api.websocket_command(
        {
            vol.Required("type"): WS_TYPE_LABEL,
            vol.Required("id"): cv.string,
            vol.Required("cycle_id"): cv.string,
            vol.Optional("program_id", default=None): vol.Any(cv.string, None),
            vol.Optional("new_program_name"): cv.string,
            vol.Optional("new_program_color"): cv.string,
        }
    )
    @websocket_api.require_admin
    @websocket_api.async_response
    async def handle_label(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Label a cycle with a program."""
        await manager.async_label_cycle(
            msg["id"],
            msg["cycle_id"],
            program_id=msg.get("program_id"),
            new_program_name=msg.get("new_program_name"),
            new_program_color=msg.get("new_program_color"),
        )
        connection.send_result(msg["id"])

    @websocket_api.websocket_command(
        {
            vol.Required("type"): WS_TYPE_PROGRAMS,
            vol.Required("id"): cv.string,
            vol.Required("programs"): [_PROGRAM_SCHEMA],
        }
    )
    @websocket_api.require_admin
    @websocket_api.async_response
    async def handle_programs(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Replace the program list of a device."""
        await manager.async_set_programs(msg["id"], msg["programs"])
        connection.send_result(msg["id"])

    @websocket_api.websocket_command(
        {
            vol.Required("type"): WS_TYPE_RESET_LEARNING,
            vol.Required("id"): cv.string,
        }
    )
    @websocket_api.require_admin
    @websocket_api.async_response
    async def handle_reset_learning(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Reset the learning data of a device."""
        await manager.async_reset_learning(msg["id"])
        connection.send_result(msg["id"])

    @websocket_api.websocket_command({vol.Required("type"): WS_TYPE_RESET_ALL})
    @websocket_api.require_admin
    @websocket_api.async_response
    async def handle_reset_all(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Remove all devices and learning data."""
        await manager.async_reset_all()
        connection.send_result(msg["id"])

    websocket_api.async_register_command(hass, handle_config)
    websocket_api.async_register_command(hass, handle_create)
    websocket_api.async_register_command(hass, handle_update)
    websocket_api.async_register_command(hass, handle_remove)
    websocket_api.async_register_command(hass, handle_label)
    websocket_api.async_register_command(hass, handle_programs)
    websocket_api.async_register_command(hass, handle_reset_learning)
    websocket_api.async_register_command(hass, handle_reset_all)
