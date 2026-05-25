"""HA Fitness Tracker integration."""
from __future__ import annotations

import logging
import sqlite3
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_EXERCISE,
    ATTR_NOTES,
    ATTR_REPS,
    ATTR_USER_ID,
    ATTR_WEIGHT,
    CONF_DISPLAY_NAME,
    CONF_INCLUDED_USER_IDS,
    DEFAULT_DISPLAY_NAME,
    DOMAIN,
    SERVICE_EXPORT_DATA,
    SERVICE_FINISH_WORKOUT,
    SERVICE_REFRESH_STATISTICS,
    SERVICE_REFRESH_USERS,
    SERVICE_SAVE_CURRENT_SET,
    SERVICE_SAVE_SET,
    SERVICE_SELECT_USER,
    SERVICE_START_WORKOUT,
)
from .coordinator import HAFitnessCoordinator
from .storage import HAFitnessStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button", "select", "number", "text"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Fitness Tracker from a config entry."""
    display_name: str = entry.data.get(CONF_DISPLAY_NAME, DEFAULT_DISPLAY_NAME)
    included_user_ids: list[str] | None = entry.options.get(CONF_INCLUDED_USER_IDS)

    try:
        store = HAFitnessStore(hass)
        await store.async_initialize()
        coordinator = HAFitnessCoordinator(hass, display_name, store, included_user_ids)
        await coordinator.async_initialize()
    except (HomeAssistantError, sqlite3.Error, OSError) as err:
        _LOGGER.error("HA Fitness setup failed: %s", err)
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        domain_entries = hass.data.get(DOMAIN)
        if domain_entries is not None:
            domain_entries.pop(entry.entry_id, None)
        if not domain_entries:
            _unregister_services(hass)
            hass.data.pop(DOMAIN, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services once (idempotent)."""
    required_services = (
        SERVICE_START_WORKOUT,
        SERVICE_FINISH_WORKOUT,
        SERVICE_SAVE_SET,
        SERVICE_SAVE_CURRENT_SET,
        SERVICE_REFRESH_STATISTICS,
        SERVICE_EXPORT_DATA,
        SERVICE_SELECT_USER,
        SERVICE_REFRESH_USERS,
    )
    if all(hass.services.has_service(DOMAIN, service) for service in required_services):
        return

    def _all_coordinators() -> list[HAFitnessCoordinator]:
        return list(hass.data.get(DOMAIN, {}).values())

    async def handle_start_workout(call: ServiceCall) -> None:
        for coordinator in _all_coordinators():
            await coordinator.start_workout(context_user_id=call.context.user_id)

    async def handle_finish_workout(call: ServiceCall) -> None:
        for coordinator in _all_coordinators():
            await coordinator.finish_workout(context_user_id=call.context.user_id)

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
            await coordinator.save_set(
                exercise=exercise,
                weight=weight,
                reps=reps,
                notes=notes,
                context_user_id=call.context.user_id,
            )

    async def handle_save_current_set(call: ServiceCall) -> None:
        for coordinator in _all_coordinators():
            await coordinator.save_current_set(context_user_id=call.context.user_id)

    async def handle_refresh_statistics(call: ServiceCall) -> None:
        for coordinator in _all_coordinators():
            await coordinator.async_refresh_statistics()

    async def handle_export_data(call: ServiceCall) -> None:
        for coordinator in _all_coordinators():
            await coordinator.async_export_data()

    async def handle_select_user(call: ServiceCall) -> None:
        user_id: str | None = call.data.get(ATTR_USER_ID)
        for coordinator in _all_coordinators():
            await coordinator.set_selected_user(user_id)

    async def handle_refresh_users(call: ServiceCall) -> None:
        for coordinator in _all_coordinators():
            await coordinator.async_refresh_users()
            await coordinator.async_refresh_statistics()

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
    hass.services.async_register(DOMAIN, SERVICE_SAVE_CURRENT_SET, handle_save_current_set)
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_STATISTICS,
        handle_refresh_statistics,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_DATA,
        handle_export_data,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SELECT_USER,
        handle_select_user,
        schema=vol.Schema({vol.Optional(ATTR_USER_ID): cv.string}),
    )
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_USERS, handle_refresh_users)


def _unregister_services(hass: HomeAssistant) -> None:
    """Remove integration services when last entry unloads."""
    for service in (
        SERVICE_START_WORKOUT,
        SERVICE_FINISH_WORKOUT,
        SERVICE_SAVE_SET,
        SERVICE_SAVE_CURRENT_SET,
        SERVICE_REFRESH_STATISTICS,
        SERVICE_EXPORT_DATA,
        SERVICE_SELECT_USER,
        SERVICE_REFRESH_USERS,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
