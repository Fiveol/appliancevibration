"""Config flow for the ApplianceVibration integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import CONF_ICON, DEFAULT_ICON, DEFAULT_NAME, DOMAIN


class ApplianceVibrationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ApplianceVibration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        self.async_abort_if_done()

        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_schema(),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the config entry."""
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._build_schema(
                defaults={
                    CONF_NAME: entry.title,
                    CONF_ICON: entry.data.get(CONF_ICON, DEFAULT_ICON),
                }
            ),
        )

    def _build_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        """Build the config flow schema."""
        defaults = defaults or {}
        return vol.Schema(
            {
                vol.Required(
                    CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)
                ): selector.TextSelector(),
                vol.Required(
                    CONF_ICON, default=defaults.get(CONF_ICON, DEFAULT_ICON)
                ): selector.IconSelector(),
            }
        )
