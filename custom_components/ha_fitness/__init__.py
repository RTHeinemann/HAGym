"""HA Fitness Tracker integration."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_EXERCISE,
    ATTR_NOTES,
    ATTR_REPS,
    ATTR_WEIGHT,
    CONF_DISPLAY_NAME,
    DEFAULT_DISPLAY_NAME,
    DOMAIN,
    SERVICE_FINISH_WORKOUT,
    SERVICE_SAVE_SET,
    SERVICE_START_WORKOUT,
)
from .coordinator import HAFitnessCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button", "select", "number", "text"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Fitness Tracker from a config entry."""
    display_name: str = entry.data.get(CONF_DISPLAY_NAME, DEFAULT_DISPLAY_NAME)
    coordinator = HAFitnessCoordinator(hass, display_name)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services once (idempotent).

    Service handlers iterate all loaded config entries so that
    every coordinator instance receives the call.
    """
    if (
        hass.services.has_service(DOMAIN, SERVICE_START_WORKOUT)
        and hass.services.has_service(DOMAIN, SERVICE_FINISH_WORKOUT)
        and hass.services.has_service(DOMAIN, SERVICE_SAVE_SET)
    ):
        return

    def _all_coordinators() -> list[HAFitnessCoordinator]:
        return list(hass.data.get(DOMAIN, {}).values())

    async def handle_start_workout(call: ServiceCall) -> None:
        for coordinator in _all_coordinators():
            coordinator.start_workout()

    async def handle_finish_workout(call: ServiceCall) -> None:
        for coordinator in _all_coordinators():
            coordinator.finish_workout()

    async def handle_save_set(call: ServiceCall) -> None:
        exercise: str = call.data[ATTR_EXERCISE]
        weight: float = call.data[ATTR_WEIGHT]
        reps: int = call.data[ATTR_REPS]
        notes: str | None = call.data.get(ATTR_NOTES)

        errors: list[str] = []
        if not exercise:
            errors.append("Exercise must not be empty.")
        if weight <= 0:
            errors.append("Weight must be greater than 0.")
        if reps <= 0:
            errors.append("Reps must be greater than 0.")

        if errors:
            message = " ".join(errors)
            _LOGGER.warning("HA Fitness save_set service validation failed: %s", message)
            raise HomeAssistantError(message)

        for coordinator in _all_coordinators():
            coordinator.save_set(
                exercise=exercise,
                weight=weight,
                reps=reps,
                notes=notes,
            )

    hass.services.async_register(DOMAIN, SERVICE_START_WORKOUT, handle_start_workout)
    hass.services.async_register(DOMAIN, SERVICE_FINISH_WORKOUT, handle_finish_workout)
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_SET,
        handle_save_set,
        schema=vol.Schema(
            {
                vol.Required(ATTR_EXERCISE): cv.string,
                vol.Required(ATTR_WEIGHT): vol.Coerce(float),
                vol.Required(ATTR_REPS): vol.Coerce(int),
                vol.Optional(ATTR_NOTES): cv.string,
            }
        ),
    )
