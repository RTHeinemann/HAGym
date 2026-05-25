"""Config flow for HA Fitness Tracker."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import CONF_DISPLAY_NAME, CONF_INCLUDED_USER_IDS, DEFAULT_DISPLAY_NAME, DOMAIN


class HAFitnessConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Fitness Tracker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_DISPLAY_NAME],
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DISPLAY_NAME, default=DEFAULT_DISPLAY_NAME
                    ): str,
                }
            ),
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return options flow for HA Fitness."""
        return HAFitnessOptionsFlow(config_entry)


class HAFitnessOptionsFlow(config_entries.OptionsFlow):
    """Options flow to configure household user filtering."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_INCLUDED_USER_IDS: user_input.get(CONF_INCLUDED_USER_IDS, []),
                },
            )

        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        users = []
        if coordinator is not None:
            users = coordinator.users

        options: list[dict[str, str]] = [
            {
                "value": str(user["id"]),
                "label": str(user.get("display_name") or user["id"]),
            }
            for user in users
            if int(user.get("enabled", 1)) == 1
        ]

        default = self.config_entry.options.get(CONF_INCLUDED_USER_IDS, [])

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_INCLUDED_USER_IDS,
                        default=default,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )
