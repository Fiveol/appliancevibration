"""ApplianceVibration integration.

Provides a config-flow driven sidebar panel with a tabbed frontend view.
"""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ICON,
    DOMAIN,
    PANEL_FILENAME,
    PANEL_STATIC_PATH,
    PANEL_URL_PATH,
    WEBCOMPONENT_NAME,
)

STATIC_PATH_REGISTERED = f"{DOMAIN}_static_path_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ApplianceVibration from a config entry.

    Serves the panel bundle over HTTP and registers the sidebar panel.
    """
    if not hass.data.get(STATIC_PATH_REGISTERED):
        panel_dir = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    PANEL_STATIC_PATH,
                    str(panel_dir / PANEL_FILENAME),
                    cache_headers=False,
                )
            ]
        )
        hass.data[STATIC_PATH_REGISTERED] = True

    await async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=WEBCOMPONENT_NAME,
        sidebar_title=entry.title,
        sidebar_icon=entry.data.get(CONF_ICON),
        module_url=PANEL_STATIC_PATH,
        config={
            "title": entry.title,
            "icon": entry.data.get(CONF_ICON),
            "version": entry.version,
        },
        require_admin=False,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry by removing its sidebar panel."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry by removing its sidebar panel."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
