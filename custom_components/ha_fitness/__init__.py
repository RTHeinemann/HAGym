"""HAGym integration."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import sqlite3
import voluptuous as vol

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from .const import (
    ATTR_ADDED_WEIGHT,
    ATTR_AVG_HEART_RATE,
    ATTR_AVG_POWER_WATTS,
    ATTR_AVG_SPEED_MPS,
    ATTR_CALORIES,
    ATTR_DISTANCE_M,
    ATTR_DURATION_SECONDS,
    ATTR_EXERCISE,
    ATTR_EXERCISE_ID,
    ATTR_ENABLED,
    ATTR_DESCRIPTION,
    ATTR_EQUIPMENT,
    ATTR_EQUIPMENT_ID,
    ATTR_MUSCLE_GROUP,
    ATTR_MUSCLE_GROUP_ID,
    ATTR_NAME_DE,
    ATTR_NAME_EN,
    ATTR_NOTES,
    ATTR_INTENSITY,
    ATTR_MAX_HEART_RATE,
    ATTR_MAX_POWER_WATTS,
    ATTR_METRIC_TYPE,
    ATTR_ROLE,
    ATTR_REPS,
    ATTR_SORT_ORDER,
    ATTR_SOURCE,
    ATTR_STEPS,
    ATTR_USER_ID,
    ATTR_WEIGHT,
    ATTR_WEIGHT_FACTOR,
    ATTR_BODY_REGION,
    ATTR_ICON,
    ATTR_CREATED_AT,
    ATTR_DELETE_SETS,
    ATTR_FORCE,
    ATTR_ENDED_AT,
    CONF_DISPLAY_NAME,
    CONF_INCLUDED_USER_IDS,
    ATTR_SET_ID,
    ATTR_STATUS,
    ATTR_STARTED_AT,
    ATTR_WORKOUT_ID,
    SERVICE_ADD_EXERCISE,
    SERVICE_ADD_SET_TO_WORKOUT,
    SERVICE_ADD_MUSCLE_GROUP,
    SERVICE_ASSIGN_MUSCLE_GROUP_TO_EXERCISE,
    SERVICE_CREATE_WORKOUT,
    SERVICE_DELETE_SET,
    SERVICE_DELETE_WORKOUT,
    SERVICE_DISABLE_MUSCLE_GROUP,
    SERVICE_DISABLE_EXERCISE,
    DEFAULT_DISPLAY_NAME,
    DOMAIN,
    SERVICE_REFRESH_EXERCISES,
    SERVICE_REFRESH_MUSCLE_GROUPS,
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
    SERVICE_UPDATE_SET,
    SERVICE_UPDATE_MUSCLE_GROUP,
    SERVICE_UPDATE_WORKOUT,
    SERVICE_SAVE_ACTIVITY,
    SUPPORTED_METRIC_TYPES,
)
from .coordinator import HAFitnessCoordinator
from .storage import HAFitnessStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button", "select", "number", "text"]
LEGACY_DISPLAY_NAMES = {"HAFitness", "HAFintess", "HA Fitness", "HA Fitness Tracker"}
_STATIC_REGISTERED_KEY = f"{DOMAIN}_static_registered"
_STATIC_URL = "/hagym_static"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HAGym from a config entry."""
    _update_legacy_entry_branding(hass, entry)
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

    await _async_register_static_path(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _reassign_equipment_entities_to_equipment_devices(hass, entry, coordinator)
    _reassign_exercise_entities_to_exercise_devices(hass, entry, coordinator)

    _register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: HAFitnessCoordinator | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is not None:
        await coordinator.async_shutdown()
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


async def _async_register_static_path(hass: HomeAssistant) -> None:
    """Expose HAGym Lovelace resources under one stable static path."""
    if hass.data.get(_STATIC_REGISTERED_KEY):
        return

    static_dir = Path(__file__).parent / "www"
    if not static_dir.exists():
        _LOGGER.debug("HAGym static directory missing, skipping %s registration", _STATIC_URL)
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig(_STATIC_URL, str(static_dir), True)]
    )
    hass.data[_STATIC_REGISTERED_KEY] = True


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
        SERVICE_ADD_MUSCLE_GROUP,
        SERVICE_UPDATE_MUSCLE_GROUP,
        SERVICE_DISABLE_MUSCLE_GROUP,
        SERVICE_ASSIGN_MUSCLE_GROUP_TO_EXERCISE,
        SERVICE_REFRESH_MUSCLE_GROUPS,
        SERVICE_CREATE_WORKOUT,
        SERVICE_UPDATE_WORKOUT,
        SERVICE_DELETE_WORKOUT,
        SERVICE_ADD_SET_TO_WORKOUT,
        SERVICE_UPDATE_SET,
        SERVICE_DELETE_SET,
        SERVICE_SAVE_ACTIVITY,
    )
    if all(hass.services.has_service(DOMAIN, service) for service in required_services):
        return

    def _all_coordinators() -> list[HAFitnessCoordinator]:
        return list(hass.data.get(DOMAIN, {}).values())

    async def handle_start_workout(call: ServiceCall) -> None:
        force = bool(call.data.get(ATTR_FORCE, False))
        for coordinator in _all_coordinators():
            await coordinator.start_workout(
                context_user_id=call.context.user_id,
                force=force,
            )

    async def handle_finish_workout(call: ServiceCall) -> None:
        force = bool(call.data.get(ATTR_FORCE, False))
        for coordinator in _all_coordinators():
            await coordinator.finish_workout(
                context_user_id=call.context.user_id,
                force=force,
            )

    async def handle_save_set(call: ServiceCall) -> None:
        exercise: str = call.data[ATTR_EXERCISE]
        weight: float = call.data[ATTR_WEIGHT]
        reps: int = call.data[ATTR_REPS]
        notes: str | None = call.data.get(ATTR_NOTES)

        errors: list[str] = []
        if not exercise:
            errors.append("Exercise must not be empty.")
        if weight < 0:
            errors.append("Weight must be >= 0.")
        if reps < 1:
            errors.append("Reps must be >= 1.")

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
            coordinator.set_active_equipment(
                equipment_id, context_user_id=call.context.user_id
            )

    async def handle_add_exercise(call: ServiceCall) -> None:
        exercise_id: str = call.data[ATTR_EXERCISE_ID].strip().lower()
        name_en: str = call.data[ATTR_NAME_EN].strip()
        name_de: str | None = _optional_str(call.data.get(ATTR_NAME_DE))
        muscle_group: str | None = _optional_str(call.data.get(ATTR_MUSCLE_GROUP))
        equipment: str | None = _optional_str(call.data.get(ATTR_EQUIPMENT))
        equipment_id: str | None = _optional_str(call.data.get(ATTR_EQUIPMENT_ID))
        metric_type: str | None = _optional_str(call.data.get(ATTR_METRIC_TYPE))
        enabled: bool = bool(call.data.get(ATTR_ENABLED, True))
        sort_order: int = int(call.data.get(ATTR_SORT_ORDER, 0))

        if not exercise_id:
            raise HomeAssistantError("exercise_id must not be empty.")
        if not name_en:
            raise HomeAssistantError("name_en must not be empty.")
        if metric_type is not None and metric_type.lower() not in SUPPORTED_METRIC_TYPES:
            raise HomeAssistantError(
                f"Unsupported metric_type '{metric_type}'. Supported values: {', '.join(SUPPORTED_METRIC_TYPES)}"
            )

        for coordinator in _all_coordinators():
            await coordinator.async_add_exercise(
                exercise_id=exercise_id,
                name_en=name_en,
                name_de=name_de,
                muscle_group=muscle_group,
                equipment=equipment,
                equipment_id=equipment_id,
                metric_type=metric_type.lower() if metric_type else None,
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
        raw_metric_type = call.data.get(ATTR_METRIC_TYPE)
        metric_type = raw_metric_type.strip().lower() if isinstance(raw_metric_type, str) else None
        enabled = call.data.get(ATTR_ENABLED)
        sort_order = call.data.get(ATTR_SORT_ORDER)

        if (
            name_en is None
            and name_de is None
            and muscle_group is None
            and equipment is None
            and equipment_id is None
            and metric_type is None
            and enabled is None
            and sort_order is None
        ):
            raise HomeAssistantError("No update fields provided for update_exercise.")
        if metric_type is not None and metric_type not in SUPPORTED_METRIC_TYPES:
            raise HomeAssistantError(
                f"Unsupported metric_type '{metric_type}'. Supported values: {', '.join(SUPPORTED_METRIC_TYPES)}"
            )

        for coordinator in _all_coordinators():
            updated = await coordinator.async_update_exercise(
                exercise_id=exercise_id,
                name_en=name_en,
                name_de=name_de,
                muscle_group=muscle_group,
                equipment=equipment,
                equipment_id=equipment_id,
                metric_type=metric_type,
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

    async def handle_add_muscle_group(call: ServiceCall) -> None:
        muscle_group_id: str = call.data[ATTR_MUSCLE_GROUP_ID].strip().lower()
        name_en: str = call.data[ATTR_NAME_EN].strip()
        name_de: str | None = _optional_str(call.data.get(ATTR_NAME_DE))
        description: str | None = _optional_str(call.data.get(ATTR_DESCRIPTION))
        icon: str | None = _optional_str(call.data.get(ATTR_ICON))
        body_region: str | None = _optional_str(call.data.get(ATTR_BODY_REGION))
        enabled: bool = bool(call.data.get(ATTR_ENABLED, True))
        sort_order: int = int(call.data.get(ATTR_SORT_ORDER, 100))

        if not muscle_group_id:
            raise HomeAssistantError("muscle_group_id must not be empty.")
        if not name_en:
            raise HomeAssistantError("name_en must not be empty.")

        for coordinator in _all_coordinators():
            await coordinator.async_add_muscle_group(
                muscle_group_id=muscle_group_id,
                name_en=name_en,
                name_de=name_de,
                description=description,
                icon=icon,
                body_region=body_region,
                enabled=enabled,
                sort_order=sort_order,
            )

    async def handle_update_muscle_group(call: ServiceCall) -> None:
        muscle_group_id: str = call.data[ATTR_MUSCLE_GROUP_ID].strip().lower()
        if not muscle_group_id:
            raise HomeAssistantError("muscle_group_id must not be empty.")

        raw_name_en = call.data.get(ATTR_NAME_EN)
        name_en = raw_name_en.strip() if isinstance(raw_name_en, str) else None
        raw_name_de = call.data.get(ATTR_NAME_DE)
        name_de = raw_name_de.strip() if isinstance(raw_name_de, str) else None
        raw_description = call.data.get(ATTR_DESCRIPTION)
        description = raw_description.strip() if isinstance(raw_description, str) else None
        raw_icon = call.data.get(ATTR_ICON)
        icon = raw_icon.strip() if isinstance(raw_icon, str) else None
        raw_body_region = call.data.get(ATTR_BODY_REGION)
        body_region = raw_body_region.strip() if isinstance(raw_body_region, str) else None
        enabled = call.data.get(ATTR_ENABLED)
        sort_order = call.data.get(ATTR_SORT_ORDER)

        if (
            name_en is None
            and name_de is None
            and description is None
            and icon is None
            and body_region is None
            and enabled is None
            and sort_order is None
        ):
            raise HomeAssistantError("No update fields provided for update_muscle_group.")

        for coordinator in _all_coordinators():
            updated = await coordinator.async_update_muscle_group(
                muscle_group_id=muscle_group_id,
                name_en=name_en,
                name_de=name_de,
                description=description,
                icon=icon,
                body_region=body_region,
                enabled=bool(enabled) if enabled is not None else None,
                sort_order=int(sort_order) if sort_order is not None else None,
            )
            if not updated:
                raise HomeAssistantError(
                    f"Muscle group '{muscle_group_id}' not found or unchanged."
                )

    async def handle_disable_muscle_group(call: ServiceCall) -> None:
        muscle_group_id: str = call.data[ATTR_MUSCLE_GROUP_ID].strip().lower()
        if not muscle_group_id:
            raise HomeAssistantError("muscle_group_id must not be empty.")
        for coordinator in _all_coordinators():
            updated = await coordinator.async_disable_muscle_group(muscle_group_id)
            if not updated:
                raise HomeAssistantError(f"Muscle group '{muscle_group_id}' not found.")

    async def handle_assign_muscle_group_to_exercise(call: ServiceCall) -> None:
        exercise_id: str = call.data[ATTR_EXERCISE_ID].strip().lower()
        muscle_group_id: str = call.data[ATTR_MUSCLE_GROUP_ID].strip().lower()
        role: str = str(call.data.get(ATTR_ROLE, "primary")).strip().lower()
        weight_factor: float = float(call.data.get(ATTR_WEIGHT_FACTOR, 1.0))
        if not exercise_id:
            raise HomeAssistantError("exercise_id must not be empty.")
        if not muscle_group_id:
            raise HomeAssistantError("muscle_group_id must not be empty.")
        for coordinator in _all_coordinators():
            await coordinator.async_assign_muscle_group_to_exercise(
                exercise_id=exercise_id,
                muscle_group_id=muscle_group_id,
                role=role,
                weight_factor=weight_factor,
            )

    async def handle_refresh_muscle_groups(call: ServiceCall) -> None:
        for coordinator in _all_coordinators():
            await coordinator.async_refresh_muscle_groups(notify=False)
            await coordinator.async_refresh_statistics()

    async def handle_create_workout(call: ServiceCall) -> None:
        started_at = _parse_datetime_input(call.data[ATTR_STARTED_AT], ATTR_STARTED_AT)
        ended_at = (
            _parse_datetime_input(call.data[ATTR_ENDED_AT], ATTR_ENDED_AT)
            if call.data.get(ATTR_ENDED_AT)
            else None
        )
        if ended_at is not None and started_at > ended_at:
            raise HomeAssistantError("started_at must be before or equal to ended_at.")
        status = _optional_str(call.data.get(ATTR_STATUS))
        notes = _optional_str(call.data.get(ATTR_NOTES))
        user_id = _optional_str(call.data.get(ATTR_USER_ID))
        for coordinator in _all_coordinators():
            try:
                await coordinator.async_create_manual_workout(
                    started_at=started_at,
                    ended_at=ended_at,
                    notes=notes,
                    status=status,
                    user_id=user_id,
                    context_user_id=call.context.user_id,
                )
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err

    async def handle_update_workout(call: ServiceCall) -> None:
        workout_id = int(call.data[ATTR_WORKOUT_ID])
        started_at = (
            _parse_datetime_input(call.data[ATTR_STARTED_AT], ATTR_STARTED_AT)
            if call.data.get(ATTR_STARTED_AT)
            else None
        )
        ended_at = (
            _parse_datetime_input(call.data[ATTR_ENDED_AT], ATTR_ENDED_AT)
            if call.data.get(ATTR_ENDED_AT)
            else None
        )
        if started_at is not None and ended_at is not None and started_at > ended_at:
            raise HomeAssistantError("started_at must be before or equal to ended_at.")
        status = _optional_str(call.data.get(ATTR_STATUS))
        notes = _optional_str(call.data.get(ATTR_NOTES))
        if started_at is None and ended_at is None and status is None and notes is None:
            raise HomeAssistantError("No update fields provided for update_workout.")
        for coordinator in _all_coordinators():
            try:
                await coordinator.async_update_existing_workout(
                    workout_id=workout_id,
                    started_at=started_at,
                    ended_at=ended_at,
                    notes=notes,
                    status=status,
                )
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err

    async def handle_delete_workout(call: ServiceCall) -> None:
        workout_id = int(call.data[ATTR_WORKOUT_ID])
        delete_sets = bool(call.data.get(ATTR_DELETE_SETS, True))
        for coordinator in _all_coordinators():
            try:
                await coordinator.async_delete_existing_workout(
                    workout_id=workout_id, delete_sets=delete_sets
                )
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err

    async def handle_add_set_to_workout(call: ServiceCall) -> None:
        workout_id = int(call.data[ATTR_WORKOUT_ID])
        exercise_id = str(call.data[ATTR_EXERCISE_ID]).strip().lower()
        equipment_id = _optional_str(call.data.get(ATTR_EQUIPMENT_ID))
        weight = float(call.data[ATTR_WEIGHT])
        reps = int(call.data[ATTR_REPS])
        notes = _optional_str(call.data.get(ATTR_NOTES))
        created_at = (
            _parse_datetime_input(call.data[ATTR_CREATED_AT], ATTR_CREATED_AT)
            if call.data.get(ATTR_CREATED_AT)
            else None
        )
        user_id = _optional_str(call.data.get(ATTR_USER_ID))
        if weight < 0:
            raise HomeAssistantError("weight must be >= 0.")
        if reps < 1:
            raise HomeAssistantError("reps must be >= 1.")
        for coordinator in _all_coordinators():
            try:
                await coordinator.async_add_set_to_existing_workout(
                    workout_id=workout_id,
                    exercise_id=exercise_id,
                    weight=weight,
                    reps=reps,
                    equipment_id=equipment_id,
                    notes=notes,
                    created_at=created_at,
                    user_id=user_id,
                    context_user_id=call.context.user_id,
                )
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err

    async def handle_save_activity(call: ServiceCall) -> None:
        workout_id_raw = call.data.get(ATTR_WORKOUT_ID)
        workout_id = int(workout_id_raw) if workout_id_raw is not None else None
        exercise_id = str(call.data[ATTR_EXERCISE_ID]).strip().lower()
        if not exercise_id:
            raise HomeAssistantError("exercise_id must not be empty.")

        raw_metric_type = call.data.get(ATTR_METRIC_TYPE)
        metric_type = (
            str(raw_metric_type).strip().lower()
            if isinstance(raw_metric_type, str) and raw_metric_type.strip()
            else None
        )
        if metric_type is not None and metric_type not in SUPPORTED_METRIC_TYPES:
            raise HomeAssistantError(
                f"Unsupported metric_type '{metric_type}'. Supported values: {', '.join(SUPPORTED_METRIC_TYPES)}"
            )

        user_id = _optional_str(call.data.get(ATTR_USER_ID))
        equipment_id = _optional_str(call.data.get(ATTR_EQUIPMENT_ID))
        notes = _optional_str(call.data.get(ATTR_NOTES))
        intensity = _optional_str(call.data.get(ATTR_INTENSITY))
        source = _optional_str(call.data.get(ATTR_SOURCE))
        created_at = (
            _parse_datetime_input(call.data[ATTR_CREATED_AT], ATTR_CREATED_AT)
            if call.data.get(ATTR_CREATED_AT)
            else None
        )

        duration_seconds = (
            int(call.data[ATTR_DURATION_SECONDS])
            if ATTR_DURATION_SECONDS in call.data
            else None
        )
        reps = int(call.data[ATTR_REPS]) if ATTR_REPS in call.data else None
        distance_m = (
            float(call.data[ATTR_DISTANCE_M]) if ATTR_DISTANCE_M in call.data else None
        )
        calories = (
            float(call.data[ATTR_CALORIES]) if ATTR_CALORIES in call.data else None
        )
        steps = int(call.data[ATTR_STEPS]) if ATTR_STEPS in call.data else None
        avg_heart_rate = (
            float(call.data[ATTR_AVG_HEART_RATE])
            if ATTR_AVG_HEART_RATE in call.data
            else None
        )
        max_heart_rate = (
            float(call.data[ATTR_MAX_HEART_RATE])
            if ATTR_MAX_HEART_RATE in call.data
            else None
        )
        avg_power_watts = (
            float(call.data[ATTR_AVG_POWER_WATTS])
            if ATTR_AVG_POWER_WATTS in call.data
            else None
        )
        max_power_watts = (
            float(call.data[ATTR_MAX_POWER_WATTS])
            if ATTR_MAX_POWER_WATTS in call.data
            else None
        )
        avg_speed_mps = (
            float(call.data[ATTR_AVG_SPEED_MPS])
            if ATTR_AVG_SPEED_MPS in call.data
            else None
        )
        added_weight = (
            float(call.data[ATTR_ADDED_WEIGHT]) if ATTR_ADDED_WEIGHT in call.data else None
        )

        if duration_seconds is not None and duration_seconds <= 0:
            raise HomeAssistantError("duration_seconds must be > 0.")
        if reps is not None and reps < 1:
            raise HomeAssistantError("reps must be >= 1.")
        if distance_m is not None and distance_m <= 0:
            raise HomeAssistantError("distance_m must be > 0.")
        if calories is not None and calories < 0:
            raise HomeAssistantError("calories must be >= 0.")
        if steps is not None and steps < 0:
            raise HomeAssistantError("steps must be >= 0.")

        for coordinator in _all_coordinators():
            try:
                await coordinator.async_save_activity(
                    exercise_id=exercise_id,
                    metric_type=metric_type,
                    user_id=user_id,
                    workout_id=workout_id,
                    equipment_id=equipment_id,
                    reps=reps,
                    duration_seconds=duration_seconds,
                    distance_m=distance_m,
                    calories=calories,
                    steps=steps,
                    avg_heart_rate=avg_heart_rate,
                    max_heart_rate=max_heart_rate,
                    avg_power_watts=avg_power_watts,
                    max_power_watts=max_power_watts,
                    avg_speed_mps=avg_speed_mps,
                    intensity=intensity,
                    source=source,
                    notes=notes,
                    created_at=created_at,
                    added_weight=added_weight,
                    context_user_id=call.context.user_id,
                )
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err

    async def handle_update_set(call: ServiceCall) -> None:
        set_id = int(call.data[ATTR_SET_ID])
        equipment_id = call.data.get(ATTR_EQUIPMENT_ID)
        if isinstance(equipment_id, str):
            equipment_id = equipment_id.strip()
        exercise_id = call.data.get(ATTR_EXERCISE_ID)
        if isinstance(exercise_id, str):
            exercise_id = exercise_id.strip().lower()
        weight = float(call.data[ATTR_WEIGHT]) if ATTR_WEIGHT in call.data else None
        reps = int(call.data[ATTR_REPS]) if ATTR_REPS in call.data else None
        notes = _optional_str(call.data.get(ATTR_NOTES)) if ATTR_NOTES in call.data else None
        created_at = (
            _parse_datetime_input(call.data[ATTR_CREATED_AT], ATTR_CREATED_AT)
            if call.data.get(ATTR_CREATED_AT)
            else None
        )
        if (
            equipment_id is None
            and exercise_id is None
            and weight is None
            and reps is None
            and notes is None
            and created_at is None
        ):
            raise HomeAssistantError("No update fields provided for update_set.")
        for coordinator in _all_coordinators():
            try:
                await coordinator.async_update_existing_set(
                    set_id=set_id,
                    equipment_id=equipment_id,
                    exercise_id=exercise_id,
                    weight=weight,
                    reps=reps,
                    notes=notes,
                    created_at=created_at,
                )
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err

    async def handle_delete_set(call: ServiceCall) -> None:
        set_id = int(call.data[ATTR_SET_ID])
        for coordinator in _all_coordinators():
            try:
                await coordinator.async_delete_existing_set(set_id)
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_WORKOUT,
        handle_start_workout,
        schema=vol.Schema({vol.Optional(ATTR_FORCE): cv.boolean}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FINISH_WORKOUT,
        handle_finish_workout,
        schema=vol.Schema({vol.Optional(ATTR_FORCE): cv.boolean}),
    )
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
                vol.Optional(ATTR_METRIC_TYPE): cv.string,
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
                vol.Optional(ATTR_METRIC_TYPE): cv.string,
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
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_MUSCLE_GROUP,
        handle_add_muscle_group,
        schema=vol.Schema(
            {
                vol.Required(ATTR_MUSCLE_GROUP_ID): cv.string,
                vol.Required(ATTR_NAME_EN): cv.string,
                vol.Optional(ATTR_NAME_DE): cv.string,
                vol.Optional(ATTR_DESCRIPTION): cv.string,
                vol.Optional(ATTR_ICON): cv.string,
                vol.Optional(ATTR_BODY_REGION): cv.string,
                vol.Optional(ATTR_ENABLED): cv.boolean,
                vol.Optional(ATTR_SORT_ORDER): vol.Coerce(int),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_MUSCLE_GROUP,
        handle_update_muscle_group,
        schema=vol.Schema(
            {
                vol.Required(ATTR_MUSCLE_GROUP_ID): cv.string,
                vol.Optional(ATTR_NAME_EN): cv.string,
                vol.Optional(ATTR_NAME_DE): cv.string,
                vol.Optional(ATTR_DESCRIPTION): cv.string,
                vol.Optional(ATTR_ICON): cv.string,
                vol.Optional(ATTR_BODY_REGION): cv.string,
                vol.Optional(ATTR_ENABLED): cv.boolean,
                vol.Optional(ATTR_SORT_ORDER): vol.Coerce(int),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DISABLE_MUSCLE_GROUP,
        handle_disable_muscle_group,
        schema=vol.Schema({vol.Required(ATTR_MUSCLE_GROUP_ID): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ASSIGN_MUSCLE_GROUP_TO_EXERCISE,
        handle_assign_muscle_group_to_exercise,
        schema=vol.Schema(
            {
                vol.Required(ATTR_EXERCISE_ID): cv.string,
                vol.Required(ATTR_MUSCLE_GROUP_ID): cv.string,
                vol.Optional(ATTR_ROLE): cv.string,
                vol.Optional(ATTR_WEIGHT_FACTOR): vol.Coerce(float),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_MUSCLE_GROUPS,
        handle_refresh_muscle_groups,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_WORKOUT,
        handle_create_workout,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_USER_ID): cv.string,
                vol.Required(ATTR_STARTED_AT): cv.string,
                vol.Optional(ATTR_ENDED_AT): cv.string,
                vol.Optional(ATTR_NOTES): cv.string,
                vol.Optional(ATTR_STATUS): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_WORKOUT,
        handle_update_workout,
        schema=vol.Schema(
            {
                vol.Required(ATTR_WORKOUT_ID): vol.Coerce(int),
                vol.Optional(ATTR_STARTED_AT): cv.string,
                vol.Optional(ATTR_ENDED_AT): cv.string,
                vol.Optional(ATTR_NOTES): cv.string,
                vol.Optional(ATTR_STATUS): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_WORKOUT,
        handle_delete_workout,
        schema=vol.Schema(
            {
                vol.Required(ATTR_WORKOUT_ID): vol.Coerce(int),
                vol.Optional(ATTR_DELETE_SETS): cv.boolean,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_SET_TO_WORKOUT,
        handle_add_set_to_workout,
        schema=vol.Schema(
            {
                vol.Required(ATTR_WORKOUT_ID): vol.Coerce(int),
                vol.Optional(ATTR_USER_ID): cv.string,
                vol.Optional(ATTR_EQUIPMENT_ID): cv.string,
                vol.Required(ATTR_EXERCISE_ID): cv.string,
                vol.Required(ATTR_WEIGHT): vol.Coerce(float),
                vol.Required(ATTR_REPS): vol.Coerce(int),
                vol.Optional(ATTR_NOTES): cv.string,
                vol.Optional(ATTR_CREATED_AT): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_ACTIVITY,
        handle_save_activity,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_USER_ID): cv.string,
                vol.Optional(ATTR_WORKOUT_ID): vol.Coerce(int),
                vol.Optional(ATTR_EQUIPMENT_ID): cv.string,
                vol.Required(ATTR_EXERCISE_ID): cv.string,
                vol.Optional(ATTR_METRIC_TYPE): cv.string,
                vol.Optional(ATTR_REPS): vol.Coerce(int),
                vol.Optional(ATTR_DURATION_SECONDS): vol.Coerce(int),
                vol.Optional(ATTR_DISTANCE_M): vol.Coerce(float),
                vol.Optional(ATTR_CALORIES): vol.Coerce(float),
                vol.Optional(ATTR_STEPS): vol.Coerce(int),
                vol.Optional(ATTR_AVG_HEART_RATE): vol.Coerce(float),
                vol.Optional(ATTR_MAX_HEART_RATE): vol.Coerce(float),
                vol.Optional(ATTR_AVG_POWER_WATTS): vol.Coerce(float),
                vol.Optional(ATTR_MAX_POWER_WATTS): vol.Coerce(float),
                vol.Optional(ATTR_AVG_SPEED_MPS): vol.Coerce(float),
                vol.Optional(ATTR_ADDED_WEIGHT): vol.Coerce(float),
                vol.Optional(ATTR_INTENSITY): cv.string,
                vol.Optional(ATTR_SOURCE): cv.string,
                vol.Optional(ATTR_NOTES): cv.string,
                vol.Optional(ATTR_CREATED_AT): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_SET,
        handle_update_set,
        schema=vol.Schema(
            {
                vol.Required(ATTR_SET_ID): vol.Coerce(int),
                vol.Optional(ATTR_EQUIPMENT_ID): cv.string,
                vol.Optional(ATTR_EXERCISE_ID): cv.string,
                vol.Optional(ATTR_WEIGHT): vol.Coerce(float),
                vol.Optional(ATTR_REPS): vol.Coerce(int),
                vol.Optional(ATTR_NOTES): cv.string,
                vol.Optional(ATTR_CREATED_AT): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_SET,
        handle_delete_set,
        schema=vol.Schema({vol.Required(ATTR_SET_ID): vol.Coerce(int)}),
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
        SERVICE_ADD_MUSCLE_GROUP,
        SERVICE_UPDATE_MUSCLE_GROUP,
        SERVICE_DISABLE_MUSCLE_GROUP,
        SERVICE_ASSIGN_MUSCLE_GROUP_TO_EXERCISE,
        SERVICE_REFRESH_MUSCLE_GROUPS,
        SERVICE_CREATE_WORKOUT,
        SERVICE_UPDATE_WORKOUT,
        SERVICE_DELETE_WORKOUT,
        SERVICE_ADD_SET_TO_WORKOUT,
        SERVICE_SAVE_ACTIVITY,
        SERVICE_UPDATE_SET,
        SERVICE_DELETE_SET,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)


def _optional_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _parse_datetime_input(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise HomeAssistantError(f"{field_name} must be a non-empty ISO datetime string.")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as err:
        raise HomeAssistantError(f"Invalid ISO datetime for {field_name}: {value}") from err
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _update_legacy_entry_branding(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rename old default config entry/display names to HAGym."""
    data = dict(entry.data)
    needs_update = False

    display_name = data.get(CONF_DISPLAY_NAME)
    if display_name in LEGACY_DISPLAY_NAMES:
        data[CONF_DISPLAY_NAME] = DEFAULT_DISPLAY_NAME
        needs_update = True

    title = DEFAULT_DISPLAY_NAME if entry.title in LEGACY_DISPLAY_NAMES else None
    if title is not None and needs_update:
        hass.config_entries.async_update_entry(entry, title=title, data=data)
    elif title is not None:
        hass.config_entries.async_update_entry(entry, title=title)
    elif needs_update:
        hass.config_entries.async_update_entry(entry, data=data)


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


def _reassign_exercise_entities_to_exercise_devices(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: HAFitnessCoordinator
) -> None:
    """Move legacy exercise-scoped entities from the tracker to exercise devices."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    exercise_ids = [
        exercise_id
        for row in coordinator.exercises
        if isinstance((exercise_id := row.get("id")), str) and exercise_id.strip()
    ]
    if not exercise_ids:
        return

    device_id_by_exercise: dict[str, str] = {}
    for exercise_id in exercise_ids:
        exercise_key = exercise_id.lower().replace(" ", "_").replace("-", "_")
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, entry.entry_id, "exercise", exercise_key)}
        )
        if device_entry is not None:
            device_id_by_exercise[exercise_key] = device_entry.id

    if not device_id_by_exercise:
        return

    entry_prefix = f"{entry.entry_id}_"
    exercise_entity_prefixes = (
        "pr",
        "volume",
        "personal_pr",
        "personal_volume",
        "household_pr",
        "household_volume",
    )

    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        unique_id = entity_entry.unique_id
        if not unique_id or not unique_id.startswith(entry_prefix):
            continue

        unique_suffix = unique_id[len(entry_prefix) :]
        matched_exercise_key = None
        for sensor_prefix in exercise_entity_prefixes:
            prefix_marker = f"{sensor_prefix}_"
            if not unique_suffix.startswith(prefix_marker):
                continue
            exercise_key = unique_suffix[len(prefix_marker) :]
            if exercise_key.endswith("_total"):
                exercise_key = exercise_key[: -len("_total")]
            if exercise_key in device_id_by_exercise:
                matched_exercise_key = exercise_key
                break

        if matched_exercise_key is None:
            continue

        target_device_id = device_id_by_exercise[matched_exercise_key]
        if entity_entry.device_id == target_device_id:
            continue

        entity_registry.async_update_entity(
            entity_entry.entity_id,
            device_id=target_device_id,
        )
