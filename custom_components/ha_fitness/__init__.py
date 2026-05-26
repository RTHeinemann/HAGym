"""HAGym integration."""
from __future__ import annotations

import logging
import sqlite3
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from .const import (
    ATTR_EXERCISE,
    ATTR_EXERCISE_ID,
    ATTR_ENABLED,
    ATTR_EQUIPMENT,
    ATTR_EQUIPMENT_ID,
    ATTR_MUSCLE_GROUP,
    ATTR_NAME_DE,
    ATTR_NAME_EN,
    ATTR_NOTES,
    ATTR_REPS,
    ATTR_SORT_ORDER,
    ATTR_USER_ID,
    ATTR_WEIGHT,
    CONF_DISPLAY_NAME,
    CONF_INCLUDED_USER_IDS,
    SERVICE_ADD_EXERCISE,
    SERVICE_DISABLE_EXERCISE,
    DEFAULT_DISPLAY_NAME,
    DOMAIN,
    SERVICE_REFRESH_EXERCISES,
    SERVICE_EXPORT_DATA,
    SERVICE_FINISH_WORKOUT,
    SERVICE_REFRESH_STATISTICS,
    SERVICE_REFRESH_USERS,
    SERVICE_SAVE_CURRENT_SET,
    SERVICE_SAVE_SET,
    SERVICE_SELECT_USER,
    SERVICE_SELECT_EQUIPMENT,
    SERVICE_START_WORKOUT,
    SERVICE_UPDATE_EXERCISE,
)
from .coordinator import HAFitnessCoordinator
from .storage import HAFitnessStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button", "select", "number", "text"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HAGym from a config entry."""
    display_name: str = entry.data.get(CONF_DISPLAY_NAME, DEFAULT_DISPLAY_NAME)
    included_user_ids: list[str] | None = entry.options.get(CONF_INCLUDED_USER_IDS)

    try:
        store = HAFitnessStore(hass)
        await store.async_initialize()
        coordinator = HAFitnessCoordinator(hass, display_name, store, included_user_ids)
        await coordinator.async_initialize()
    except (HomeAssistantError, sqlite3.Error, OSError) as err:
        _LOGGER.error("HAGym setup failed: %s", err)
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _reassign_equipment_entities_to_equipment_devices(hass, entry, coordinator)

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
        SERVICE_SELECT_EQUIPMENT,
        SERVICE_ADD_EXERCISE,
        SERVICE_UPDATE_EXERCISE,
        SERVICE_DISABLE_EXERCISE,
        SERVICE_REFRESH_EXERCISES,
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
            _LOGGER.warning("HAGym save_set service validation failed: %s", message)
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

    async def handle_select_equipment(call: ServiceCall) -> None:
        raw_equipment_id = call.data.get(ATTR_EQUIPMENT_ID)
        equipment_id = (
            raw_equipment_id.strip().lower()
            if isinstance(raw_equipment_id, str) and raw_equipment_id.strip()
            else None
        )
        for coordinator in _all_coordinators():
            coordinator.set_active_equipment(equipment_id)

    async def handle_add_exercise(call: ServiceCall) -> None:
        exercise_id: str = call.data[ATTR_EXERCISE_ID].strip().lower()
        name_en: str = call.data[ATTR_NAME_EN].strip()
        name_de: str | None = _optional_str(call.data.get(ATTR_NAME_DE))
        muscle_group: str | None = _optional_str(call.data.get(ATTR_MUSCLE_GROUP))
        equipment: str | None = _optional_str(call.data.get(ATTR_EQUIPMENT))
        equipment_id: str | None = _optional_str(call.data.get(ATTR_EQUIPMENT_ID))
        enabled: bool = bool(call.data.get(ATTR_ENABLED, True))
        sort_order: int = int(call.data.get(ATTR_SORT_ORDER, 0))

        if not exercise_id:
            raise HomeAssistantError("exercise_id must not be empty.")
        if not name_en:
            raise HomeAssistantError("name_en must not be empty.")

        for coordinator in _all_coordinators():
            await coordinator.async_add_exercise(
                exercise_id=exercise_id,
                name_en=name_en,
                name_de=name_de,
                muscle_group=muscle_group,
                equipment=equipment,
                equipment_id=equipment_id,
                enabled=enabled,
                sort_order=sort_order,
            )

    async def handle_update_exercise(call: ServiceCall) -> None:
        exercise_id: str = call.data[ATTR_EXERCISE_ID].strip().lower()
        if not exercise_id:
            raise HomeAssistantError("exercise_id must not be empty.")

        raw_name_en = call.data.get(ATTR_NAME_EN)
        name_en = raw_name_en.strip() if isinstance(raw_name_en, str) else None
        raw_name_de = call.data.get(ATTR_NAME_DE)
        name_de = raw_name_de.strip() if isinstance(raw_name_de, str) else None
        raw_muscle_group = call.data.get(ATTR_MUSCLE_GROUP)
        muscle_group = raw_muscle_group.strip() if isinstance(raw_muscle_group, str) else None
        raw_equipment = call.data.get(ATTR_EQUIPMENT)
        equipment = raw_equipment.strip() if isinstance(raw_equipment, str) else None
        raw_equipment_id = call.data.get(ATTR_EQUIPMENT_ID)
        equipment_id = raw_equipment_id.strip() if isinstance(raw_equipment_id, str) else None
        enabled = call.data.get(ATTR_ENABLED)
        sort_order = call.data.get(ATTR_SORT_ORDER)

        if (
            name_en is None
            and name_de is None
            and muscle_group is None
            and equipment is None
            and equipment_id is None
            and enabled is None
            and sort_order is None
        ):
            raise HomeAssistantError("No update fields provided for update_exercise.")

        for coordinator in _all_coordinators():
            updated = await coordinator.async_update_exercise(
                exercise_id=exercise_id,
                name_en=name_en,
                name_de=name_de,
                muscle_group=muscle_group,
                equipment=equipment,
                equipment_id=equipment_id,
                enabled=bool(enabled) if enabled is not None else None,
                sort_order=int(sort_order) if sort_order is not None else None,
            )
            if not updated:
                raise HomeAssistantError(f"Exercise '{exercise_id}' not found or unchanged.")

    async def handle_disable_exercise(call: ServiceCall) -> None:
        exercise_id: str = call.data[ATTR_EXERCISE_ID].strip().lower()
        if not exercise_id:
            raise HomeAssistantError("exercise_id must not be empty.")

        for coordinator in _all_coordinators():
            updated = await coordinator.async_disable_exercise(exercise_id)
            if not updated:
                raise HomeAssistantError(f"Exercise '{exercise_id}' not found.")

    async def handle_refresh_exercises(call: ServiceCall) -> None:
        for coordinator in _all_coordinators():
            await coordinator.async_reload_exercise_catalog()

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
    hass.services.async_register(
        DOMAIN,
        SERVICE_SELECT_EQUIPMENT,
        handle_select_equipment,
        schema=vol.Schema({vol.Optional(ATTR_EQUIPMENT_ID): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_EXERCISE,
        handle_add_exercise,
        schema=vol.Schema(
            {
                vol.Required(ATTR_EXERCISE_ID): cv.string,
                vol.Required(ATTR_NAME_EN): cv.string,
                vol.Optional(ATTR_NAME_DE): cv.string,
                vol.Optional(ATTR_MUSCLE_GROUP): cv.string,
                vol.Optional(ATTR_EQUIPMENT): cv.string,
                vol.Optional(ATTR_EQUIPMENT_ID): cv.string,
                vol.Optional(ATTR_ENABLED): cv.boolean,
                vol.Optional(ATTR_SORT_ORDER): vol.Coerce(int),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_EXERCISE,
        handle_update_exercise,
        schema=vol.Schema(
            {
                vol.Required(ATTR_EXERCISE_ID): cv.string,
                vol.Optional(ATTR_NAME_EN): cv.string,
                vol.Optional(ATTR_NAME_DE): cv.string,
                vol.Optional(ATTR_MUSCLE_GROUP): cv.string,
                vol.Optional(ATTR_EQUIPMENT): cv.string,
                vol.Optional(ATTR_EQUIPMENT_ID): cv.string,
                vol.Optional(ATTR_ENABLED): cv.boolean,
                vol.Optional(ATTR_SORT_ORDER): vol.Coerce(int),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DISABLE_EXERCISE,
        handle_disable_exercise,
        schema=vol.Schema({vol.Required(ATTR_EXERCISE_ID): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_EXERCISES,
        handle_refresh_exercises,
    )


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
        SERVICE_SELECT_EQUIPMENT,
        SERVICE_ADD_EXERCISE,
        SERVICE_UPDATE_EXERCISE,
        SERVICE_DISABLE_EXERCISE,
        SERVICE_REFRESH_EXERCISES,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)


def _optional_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _reassign_equipment_entities_to_equipment_devices(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: HAFitnessCoordinator
) -> None:
    """Move legacy equipment-scoped entities to their equipment devices."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    equipment_ids = [
        equipment_id
        for row in coordinator.equipment
        if isinstance((equipment_id := row.get("id")), str) and equipment_id.strip()
    ]
    if not equipment_ids:
        return

    device_id_by_equipment: dict[str, str] = {}
    for equipment_id in equipment_ids:
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, entry.entry_id, equipment_id)}
        )
        if device_entry is not None:
            device_id_by_equipment[equipment_id] = device_entry.id

    if not device_id_by_equipment:
        return

    entry_prefix = f"{entry.entry_id}_"
    equipment_entity_suffixes = (
        "select_equipment",
        "last_set",
        "personal_total_volume",
        "household_total_volume",
        "total_volume",
        "total_sets",
        "personal_total_sets",
        "household_total_sets",
        "top_exercise",
        "last_used",
        "total_trainings",
    )

    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        unique_id = entity_entry.unique_id
        if not unique_id or not unique_id.startswith(entry_prefix):
            continue

        unique_suffix = unique_id[len(entry_prefix) :]
        matched_equipment_id = None
        for sensor_suffix in equipment_entity_suffixes:
            suffix_marker = f"_{sensor_suffix}"
            if not unique_suffix.endswith(suffix_marker):
                continue
            equipment_id = unique_suffix[: -len(suffix_marker)]
            if equipment_id in device_id_by_equipment:
                matched_equipment_id = equipment_id
                break

        if matched_equipment_id is None:
            continue

        target_device_id = device_id_by_equipment[matched_equipment_id]
        if entity_entry.device_id == target_device_id:
            continue

        entity_registry.async_update_entity(
            entity_entry.entity_id,
            device_id=target_device_id,
        )
