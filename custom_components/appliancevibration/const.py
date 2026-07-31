"""Constants for the ApplianceVibration integration."""

from homeassistant.const import Platform

DOMAIN = "appliancevibration"

CONF_ICON = "icon"

DEFAULT_NAME = "Appliance Vibration"
DEFAULT_ICON = "mdi:vibrate"

# Sidebar panel
PANEL_URL_PATH = DOMAIN
WEBCOMPONENT_NAME = "appliance-vibration-panel"
PANEL_FILENAME = "panel.js"
PANEL_STATIC_PATH = f"/api/{DOMAIN}/panel"
PANEL_HEADER = "appliancevibration-header"

PLATFORMS: list[Platform] = []
