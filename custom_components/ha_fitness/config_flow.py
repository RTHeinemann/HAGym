"""Config flow for HAGym."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    ATTR_BODY_REGION,
    ATTR_BODYWEIGHT_FACTOR,
    ATTR_DESCRIPTION,
    ATTR_ENABLED,
    ATTR_EQUIPMENT,
    ATTR_EQUIPMENT_ID,
    ATTR_EXERCISE_ID,
    ATTR_ICON,
    ATTR_LOCATION,
    ATTR_METRIC_TYPE,
    ATTR_MUSCLE_GROUP,
    ATTR_MUSCLE_GROUP_ID,
    ATTR_NAME_DE,
    ATTR_NAME_EN,
    ATTR_NOTES,
    ATTR_REPS,
    ATTR_SORT_ORDER,
    ATTR_USES_BODYWEIGHT,
    ATTR_WEIGHT,
    CONF_DISPLAY_NAME,
    CONF_INCLUDED_USER_IDS,
    DEFAULT_DISPLAY_NAME,
    DOMAIN,
    METRIC_TYPE_BODYWEIGHT,
    METRIC_TYPE_CARDIO,
    METRIC_TYPE_CUSTOM,
    METRIC_TYPE_DISTANCE,
    METRIC_TYPE_DURATION,
    METRIC_TYPE_HOLD,
    METRIC_TYPE_STRENGTH,
)
from .storage import HAFitnessStore

_LOGGER = logging.getLogger(__name__)

_EXERCISE_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
_EQUIPMENT_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
_MUSCLE_GROUP_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
_DEFAULT_SORT_ORDER = 100
_MUSCLE_GROUP_OPTIONS = [
    "chest",
    "back",
    "legs",
    "shoulders",
    "biceps",
    "triceps",
    "core",
    "posterior_chain",
    "full_body",
    "other",
]
_EQUIPMENT_OPTIONS = [
    "barbell",
    "dumbbell",
    "machine",
    "cable",
    "bodyweight",
    "kettlebell",
    "resistance_band",
    "other",
]
_METRIC_TYPE_OPTIONS = [
    METRIC_TYPE_STRENGTH,
    METRIC_TYPE_BODYWEIGHT,
    METRIC_TYPE_DURATION,
    METRIC_TYPE_DISTANCE,
    METRIC_TYPE_CARDIO,
    METRIC_TYPE_HOLD,
    METRIC_TYPE_CUSTOM,
]


def _get_stored_bodyweight_factor(exercise: dict[str, Any]) -> float:
    """Return stored bodyweight factor from exercise dict.

    Returns 1.0 only when the key is truly missing or None (legacy row).
    A stored value of 0.0 is preserved — never replaced by the default.
    """
    raw = exercise.get(ATTR_BODYWEIGHT_FACTOR)
    if raw is None:
        return 1.0
    return float(raw)


def _bodyweight_factor_to_percent(exercise: dict[str, Any]) -> int:
    """Convert stored factor to percentage for form display (0–100)."""
    return int(round(_get_stored_bodyweight_factor(exercise) * 100))


class HAFitnessConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HAGym."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the initial step.

        If HAGym is already configured, offer direct add shortcuts instead
        of creating a second independent entry.
        """
        try:
            existing = self._async_current_entries()
            if existing:
                return await self.async_step_add_shortcut()
        except Exception:
            _LOGGER.exception("HAGym config flow user step failed")
            return self.async_abort(reason="unknown")

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

    async def async_step_add_equipment(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Add a fitness equipment device when HAGym is already configured.

        This step acts as the "Add Device" flow for the integration.
        Equipment is global / shared across all HA users.
        After saving, the integration reloads to create the new HA device and entities.
        """
        errors: dict[str, str] = {}

        existing_entries = self._async_current_entries()
        if not existing_entries:
            return await self.async_step_user(user_input)

        entry = existing_entries[0]
        coordinator = self.hass.data.get(DOMAIN, {}).get(entry.entry_id)

        if user_input is not None:
            try:
                equipment_id = _normalize_equipment_id(
                    str(user_input.get(ATTR_EQUIPMENT_ID, ""))
                )
                name_de = str(user_input.get(ATTR_NAME_DE, "")).strip()
                name_en = _optional_str(user_input.get(ATTR_NAME_EN))
                description = _optional_str(user_input.get(ATTR_DESCRIPTION))
                icon = _optional_str(user_input.get(ATTR_ICON))
                location = _optional_str(user_input.get(ATTR_LOCATION))
                enabled = bool(user_input.get(ATTR_ENABLED, True))
                sort_order_raw = user_input.get(ATTR_SORT_ORDER, _DEFAULT_SORT_ORDER)
                sort_order = _coerce_int(sort_order_raw, _DEFAULT_SORT_ORDER)

                if not equipment_id:
                    errors[ATTR_EQUIPMENT_ID] = "invalid_equipment_id"
                elif coordinator is not None and coordinator.get_equipment(equipment_id):
                    errors[ATTR_EQUIPMENT_ID] = "equipment_exists"
                elif equipment_id and coordinator is None:
                    store_check = HAFitnessStore(self.hass)
                    await store_check.async_initialize()
                    if await store_check.async_get_equipment(equipment_id) is not None:
                        errors[ATTR_EQUIPMENT_ID] = "equipment_exists"
                if not name_de:
                    errors[ATTR_NAME_DE] = "name_required"
                if not _is_valid_sort_order_input(sort_order_raw):
                    errors[ATTR_SORT_ORDER] = "invalid_sort_order"

                if not errors:
                    resolved_name_en = name_en or name_de
                    if coordinator is not None:
                        await coordinator.async_add_equipment(
                            equipment_id=equipment_id,
                            name=name_de,
                            name_en=resolved_name_en,
                            name_de=name_de,
                            description=description,
                            icon=icon,
                            location=location,
                            enabled=enabled,
                            sort_order=sort_order,
                        )
                    else:
                        store = HAFitnessStore(self.hass)
                        await store.async_initialize()
                        await store.async_add_equipment(
                            equipment_id=equipment_id,
                            name=name_de,
                            name_en=resolved_name_en,
                            name_de=name_de,
                            description=description,
                            icon=icon,
                            location=location,
                            enabled=enabled,
                            sort_order=sort_order,
                        )

                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(entry.entry_id)
                    )
                    return self.async_abort(reason="equipment_added_reload_required")
            except Exception:
                _LOGGER.exception("HAGym add_equipment config flow step failed")
                errors["base"] = "unknown_error"

        return self.async_show_form(
            step_id="add_equipment",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        ATTR_EQUIPMENT_ID,
                        default=str(user_input.get(ATTR_EQUIPMENT_ID, ""))
                        if user_input
                        else "",
                    ): str,
                    vol.Required(
                        ATTR_NAME_DE,
                        default=str(user_input.get(ATTR_NAME_DE, "")) if user_input else "",
                    ): str,
                    vol.Optional(
                        ATTR_NAME_EN,
                        default=str(user_input.get(ATTR_NAME_EN, "")) if user_input else "",
                    ): str,
                    vol.Optional(
                        ATTR_DESCRIPTION,
                        default=str(user_input.get(ATTR_DESCRIPTION, ""))
                        if user_input
                        else "",
                    ): str,
                    vol.Optional(
                        ATTR_ICON,
                        default=str(user_input.get(ATTR_ICON, ""))
                        if user_input
                        else "mdi:dumbbell",
                    ): str,
                    vol.Optional(
                        ATTR_LOCATION,
                        default=str(user_input.get(ATTR_LOCATION, ""))
                        if user_input
                        else "",
                    ): str,
                    vol.Optional(
                        ATTR_SORT_ORDER,
                        default=user_input.get(ATTR_SORT_ORDER, _DEFAULT_SORT_ORDER)
                        if user_input
                        else _DEFAULT_SORT_ORDER,
                    ): NumberSelector(
                        NumberSelectorConfig(min=0, max=9999, step=1, mode="box")
                    ),
                    vol.Optional(
                        ATTR_ENABLED,
                        default=bool(user_input.get(ATTR_ENABLED, True))
                        if user_input
                        else True,
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_add_shortcut(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Offer direct add shortcuts for an existing HAGym entry."""
        if not self._async_current_entries():
            return await self.async_step_user(user_input)

        return self.async_show_menu(
            step_id="add_shortcut",
            menu_options=["add_equipment", "add_exercise"],
        )

    async def async_step_add_exercise(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Add a fitness exercise device when HAGym is already configured."""
        errors: dict[str, str] = {}

        existing_entries = self._async_current_entries()
        if not existing_entries:
            return await self.async_step_user(user_input)

        entry = existing_entries[0]
        coordinator = self.hass.data.get(DOMAIN, {}).get(entry.entry_id)

        if user_input is not None:
            try:
                normalized_exercise_id = _normalize_exercise_id(
                    str(user_input.get(ATTR_EXERCISE_ID, ""))
                )
                name_en = str(user_input.get(ATTR_NAME_EN, "")).strip()
                name_de = _optional_str(user_input.get(ATTR_NAME_DE))
                muscle_group = _optional_str(user_input.get(ATTR_MUSCLE_GROUP))
                equipment = _optional_str(user_input.get(ATTR_EQUIPMENT))
                equipment_id = _optional_str(user_input.get(ATTR_EQUIPMENT_ID))
                metric_type = _optional_str(user_input.get(ATTR_METRIC_TYPE))
                enabled = bool(user_input.get(ATTR_ENABLED, True))
                sort_order_raw = user_input.get(ATTR_SORT_ORDER, _DEFAULT_SORT_ORDER)
                sort_order = _coerce_int(sort_order_raw, _DEFAULT_SORT_ORDER)

                # Bodyweight fields
                uses_bodyweight = bool(user_input.get(ATTR_USES_BODYWEIGHT, False))
                bodyweight_pct_raw = user_input.get(ATTR_BODYWEIGHT_FACTOR, 100)
                try:
                    bodyweight_factor = round(float(bodyweight_pct_raw) / 100.0, 4)
                except (TypeError, ValueError):
                    bodyweight_factor = 1.0
                bodyweight_factor = max(0.0, min(1.0, bodyweight_factor))

                if not normalized_exercise_id:
                    errors[ATTR_EXERCISE_ID] = "invalid_exercise_id"
                elif (
                    coordinator is not None
                    and coordinator.get_exercise(normalized_exercise_id)
                ):
                    errors[ATTR_EXERCISE_ID] = "exercise_exists"
                elif normalized_exercise_id and coordinator is None:
                    store_check = HAFitnessStore(self.hass)
                    await store_check.async_initialize()
                    if (
                        await store_check.async_get_exercise(normalized_exercise_id)
                        is not None
                    ):
                        errors[ATTR_EXERCISE_ID] = "exercise_exists"

                if not name_en:
                    errors[ATTR_NAME_EN] = "name_required"
                if metric_type is not None and metric_type not in _METRIC_TYPE_OPTIONS:
                    errors[ATTR_METRIC_TYPE] = "invalid_metric_type"
                if not _is_valid_sort_order_input(sort_order_raw):
                    errors[ATTR_SORT_ORDER] = "invalid_sort_order"

                if not errors:
                    if coordinator is not None:
                        await coordinator.async_add_exercise(
                            exercise_id=normalized_exercise_id,
                            name_en=name_en,
                            name_de=name_de,
                            muscle_group=muscle_group,
                            equipment=equipment,
                            equipment_id=equipment_id,
                            metric_type=metric_type,
                            enabled=enabled,
                            sort_order=sort_order,
                            uses_bodyweight=uses_bodyweight,
                            bodyweight_factor=bodyweight_factor,
                        )
                    else:
                        store = HAFitnessStore(self.hass)
                        await store.async_initialize()
                        await store.async_add_exercise(
                            exercise_id=normalized_exercise_id,
                            name_en=name_en,
                            name_de=name_de,
                            muscle_group=muscle_group,
                            equipment=equipment,
                            equipment_id=equipment_id,
                            metric_type=metric_type,
                            enabled=enabled,
                            sort_order=sort_order,
                            uses_bodyweight=uses_bodyweight,
                            bodyweight_factor=bodyweight_factor,
                        )

                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(entry.entry_id)
                    )
                    return self.async_abort(reason="exercise_added_reload_required")
            except Exception:
                _LOGGER.exception("HAGym add_exercise config flow step failed")
                errors["base"] = "unknown_error"

        return self.async_show_form(
            step_id="add_exercise",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        ATTR_EXERCISE_ID,
                        default=str(user_input.get(ATTR_EXERCISE_ID, ""))
                        if user_input
                        else "",
                    ): str,
                    vol.Required(
                        ATTR_NAME_EN,
                        default=str(user_input.get(ATTR_NAME_EN, ""))
                        if user_input
                        else "",
                    ): str,
                    vol.Optional(
                        ATTR_NAME_DE,
                        default=str(user_input.get(ATTR_NAME_DE, ""))
                        if user_input
                        else "",
                    ): str,
                    vol.Optional(
                        ATTR_MUSCLE_GROUP,
                        default=str(user_input.get(ATTR_MUSCLE_GROUP, ""))
                        if user_input
                        else "",
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_selector_options(_MUSCLE_GROUP_OPTIONS),
                            mode="dropdown",
                            custom_value=True,
                        )
                    ),
                    vol.Optional(
                        ATTR_EQUIPMENT,
                        default=str(user_input.get(ATTR_EQUIPMENT, ""))
                        if user_input
                        else "",
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_selector_options(_EQUIPMENT_OPTIONS),
                            mode="dropdown",
                            custom_value=True,
                        )
                    ),
                    vol.Optional(
                        ATTR_EQUIPMENT_ID,
                        default=str(user_input.get(ATTR_EQUIPMENT_ID, ""))
                        if user_input
                        else "",
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_selector_options_from_rows(
                                coordinator.get_equipment_options(
                                    include_disabled=False
                                )
                            )
                            if coordinator
                            else [],
                            mode="dropdown",
                            custom_value=True,
                        )
                    ),
                    vol.Optional(
                        ATTR_METRIC_TYPE,
                        default=str(user_input.get(ATTR_METRIC_TYPE, METRIC_TYPE_STRENGTH))
                        if user_input
                        else METRIC_TYPE_STRENGTH,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_selector_options(_METRIC_TYPE_OPTIONS),
                            mode="dropdown",
                            custom_value=False,
                        )
                    ),
                    vol.Optional(
                        ATTR_SORT_ORDER,
                        default=user_input.get(ATTR_SORT_ORDER, _DEFAULT_SORT_ORDER)
                        if user_input
                        else _DEFAULT_SORT_ORDER,
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=9999,
                            step=1,
                            mode="box",
                        )
                    ),
                    vol.Optional(
                        ATTR_ENABLED,
                        default=bool(user_input.get(ATTR_ENABLED, True))
                        if user_input
                        else True,
                    ): bool,
                    # Bodyweight support fields (ConfigFlow add_exercise)
                    vol.Optional(
                        ATTR_USES_BODYWEIGHT,
                        default=bool(user_input.get(ATTR_USES_BODYWEIGHT, False))
                        if user_input
                        else False,
                    ): bool,
                    vol.Optional(
                        ATTR_BODYWEIGHT_FACTOR,
                        default=round(float(user_input.get(ATTR_BODYWEIGHT_FACTOR, 100)))
                        if user_input is not None and ATTR_BODYWEIGHT_FACTOR in user_input
                        else 100,
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=1,
                            mode="box",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> HAFitnessOptionsFlow:
        """Return options flow for HAGym."""
        return HAFitnessOptionsFlow()


class HAFitnessOptionsFlow(config_entries.OptionsFlow):
    """Options flow for household users and exercise management."""

    def __init__(self) -> None:
        self._selected_exercise_id: str | None = None
        self._selected_equipment_id: str | None = None
        self._selected_muscle_group_id: str | None = None
        self._selected_workout_id: int | None = None
        self._selected_set_id: int | None = None
        self._assign_muscle_exercise_id: str | None = None
        self._assign_primary_muscle_group_ids: list[str] = []
        self._assign_secondary_muscle_group_ids: list[str] = []
        self._assign_stabilizer_muscle_group_ids: list[str] = []
        # Normalized weight factors (0.0-1.0) keyed by muscle_group_id
        self._assign_weight_factors: dict[str, float] = {}

    @property
    def _coordinator(self):
        return self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Show options root menu."""
        try:
            return self.async_show_menu(
                step_id="init",
                menu_options=[
                    "configure_household_users",
                    "manage_exercises",
                    "manage_equipment",
                    "manage_muscle_groups",
                    "manage_workouts",
                    "add_exercise",
                    "edit_exercise_select",
                    "toggle_exercise_select",
                    "add_equipment",
                    "edit_equipment_select",
                    "toggle_equipment_select",
                    "assign_exercises_select_equipment",
                    "add_muscle_group",
                    "edit_muscle_group_select",
                    "toggle_muscle_group_select",
                    "assign_muscle_groups_select_exercise",
                ],
            )
        except Exception:
            _LOGGER.exception("HAGym options flow init failed")
            return self.async_abort(reason="options_flow_error")

    async def async_step_manage_exercises(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Show exercise management submenu."""
        return self.async_show_menu(
            step_id="manage_exercises",
            menu_options=[
                "add_exercise",
                "edit_exercise_select",
                "toggle_exercise_select",
                "assign_exercises_select_equipment",
                "manage_equipment",
                "manage_muscle_groups",
                "manage_workouts",
                "init",
            ],
        )

    async def async_step_manage_equipment(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Show equipment management submenu."""
        return self.async_show_menu(
            step_id="manage_equipment",
            menu_options=[
                "add_equipment",
                "edit_equipment_select",
                "toggle_equipment_select",
                "assign_exercises_select_equipment",
                "manage_exercises",
                "manage_muscle_groups",
                "manage_workouts",
                "init",
            ],
        )

    async def async_step_manage_muscle_groups(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Show muscle group management submenu."""
        return self.async_show_menu(
            step_id="manage_muscle_groups",
            menu_options=[
                "add_muscle_group",
                "edit_muscle_group_select",
                "toggle_muscle_group_select",
                "assign_muscle_groups_select_exercise",
                "manage_exercises",
                "manage_equipment",
                "manage_workouts",
                "init",
            ],
        )

    async def async_step_manage_workouts(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Show workout management submenu."""
        return self.async_show_menu(
            step_id="manage_workouts",
            menu_options=[
                "view_workout_select",
                "create_workout",
                "edit_workout_select",
                "add_set_to_workout",
                "edit_set_select_workout",
                "delete_set_select_workout",
                "delete_workout_select",
                "init",
            ],
        )

    async def async_step_view_workout_select(
        self, user_input: dict | None = None
    ) -> FlowResult:
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")

        await coordinator.async_refresh_workout_history(notify=False)
        workouts = coordinator.get_recent_workouts()
        options = [
            {
                "value": str(row.get("workout_id")),
                "label": f"#{row.get('workout_id')} {row.get('started_at')}",
            }
            for row in workouts
            if row.get("workout_id") is not None
        ]
        if not options:
            return self.async_abort(reason="workout_history_empty")

        if user_input is not None:
            raw_workout_id = str(user_input.get("workout_id") or "").strip()
            if not raw_workout_id.isdigit():
                return self.async_show_form(
                    step_id="view_workout_select",
                    data_schema=vol.Schema(
                        {
                            vol.Required("workout_id"): SelectSelector(
                                SelectSelectorConfig(
                                    options=options,
                                    multiple=False,
                                    custom_value=False,
                                    mode="dropdown",
                                )
                            )
                        }
                    ),
                    errors={"workout_id": "workout_not_found"},
                )
            self._selected_workout_id = int(raw_workout_id)
            return await self.async_step_view_workout_details()

        return self.async_show_form(
            step_id="view_workout_select",
            data_schema=vol.Schema(
                {
                    vol.Required("workout_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )

    async def async_step_view_workout_details(
        self, user_input: dict | None = None
    ) -> FlowResult:
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        if self._selected_workout_id is None:
            return await self.async_step_view_workout_select()
        await coordinator.async_refresh_workout_history(notify=False)
        workout = next(
            (
                row
                for row in coordinator.get_recent_workouts()
                if int(row.get("workout_id", -1)) == self._selected_workout_id
            ),
            None,
        )
        if workout is None:
            return self.async_abort(reason="workout_not_found")
        if user_input is not None:
            return await self.async_step_manage_workouts()
        set_lines = []
        for set_row in list(workout.get("sets", []))[:10]:
            set_lines.append(
                f"- #{set_row.get('set_id')} {set_row.get('exercise_name')} {set_row.get('weight')}x{set_row.get('reps')}"
            )
        sets_block = "\\n".join(set_lines) if set_lines else "- no sets"
        details = (
            f"Workout #{workout.get('workout_id')}\\n"
            f"Start: {workout.get('started_at')}\\n"
            f"End: {workout.get('ended_at')}\\n"
            f"Status: {workout.get('status')}\\n"
            f"Sets: {workout.get('total_sets')}\\n"
            f"Volume: {round(float(workout.get('total_volume', 0.0)), 2)} kg\\n"
            f"Set preview:\\n{sets_block}"
        )
        return self.async_show_form(
            step_id="view_workout_details",
            data_schema=vol.Schema({}),
            description_placeholders={"details": details},
        )

    async def async_step_create_workout(
        self, user_input: dict | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")

        if user_input is not None:
            try:
                started_at = _parse_datetime_input(str(user_input.get("started_at", "")))
                ended_raw = _optional_str(user_input.get("ended_at"))
                ended_at = _parse_datetime_input(ended_raw) if ended_raw else None
                notes = _optional_str(user_input.get(ATTR_NOTES))
                status = _optional_str(user_input.get("status"))
                await coordinator.async_create_manual_workout(
                    started_at=started_at,
                    ended_at=ended_at,
                    notes=notes,
                    status=status,
                )
                return await self.async_step_manage_workouts()
            except HomeAssistantError:
                errors["base"] = "options_flow_error"
            except Exception:
                _LOGGER.exception("HAGym options flow create_workout failed")
                errors["base"] = "options_flow_error"

        return self.async_show_form(
            step_id="create_workout",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "started_at",
                        default=str(user_input.get("started_at", "")) if user_input else "",
                    ): str,
                    vol.Optional(
                        "ended_at",
                        default=str(user_input.get("ended_at", "")) if user_input else "",
                    ): str,
                    vol.Optional(
                        ATTR_NOTES,
                        default=str(user_input.get(ATTR_NOTES, "")) if user_input else "",
                    ): str,
                    vol.Optional(
                        "status",
                        default=str(user_input.get("status", "completed"))
                        if user_input
                        else "completed",
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_selector_options(["active", "completed", "cancelled"]),
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_edit_workout_select(
        self, user_input: dict | None = None
    ) -> FlowResult:
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        await coordinator.async_refresh_workout_history(notify=False)
        options = [
            {
                "value": str(row.get("workout_id")),
                "label": f"#{row.get('workout_id')} {row.get('started_at')}",
            }
            for row in coordinator.get_recent_workouts()
            if row.get("workout_id") is not None
        ]
        if not options:
            return self.async_abort(reason="workout_history_empty")
        if user_input is not None:
            raw_workout_id = str(user_input.get("workout_id") or "").strip()
            if not raw_workout_id.isdigit():
                return self.async_abort(reason="workout_not_found")
            self._selected_workout_id = int(raw_workout_id)
            return await self.async_step_edit_workout()
        return self.async_show_form(
            step_id="edit_workout_select",
            data_schema=vol.Schema(
                {
                    vol.Required("workout_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )

    async def async_step_edit_workout(
        self, user_input: dict | None = None
    ) -> FlowResult:
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        if self._selected_workout_id is None:
            return await self.async_step_edit_workout_select()
        await coordinator.async_refresh_workout_history(notify=False)
        selected = next(
            (
                row
                for row in coordinator.get_recent_workouts()
                if int(row.get("workout_id", -1)) == self._selected_workout_id
            ),
            None,
        )
        if selected is None:
            return self.async_abort(reason="workout_not_found")
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                started_raw = _optional_str(user_input.get("started_at"))
                ended_raw = _optional_str(user_input.get("ended_at"))
                started_at = _parse_datetime_input(started_raw) if started_raw else None
                ended_at = _parse_datetime_input(ended_raw) if ended_raw else None
                notes = _optional_str(user_input.get(ATTR_NOTES))
                status = _optional_str(user_input.get("status"))
                await coordinator.async_update_existing_workout(
                    workout_id=self._selected_workout_id,
                    started_at=started_at,
                    ended_at=ended_at,
                    notes=notes,
                    status=status,
                )
                return await self.async_step_manage_workouts()
            except HomeAssistantError:
                errors["base"] = "options_flow_error"
            except Exception:
                _LOGGER.exception("HAGym options flow edit_workout failed")
                errors["base"] = "options_flow_error"
        return self.async_show_form(
            step_id="edit_workout",
            data_schema=vol.Schema(
                {
                    vol.Optional("started_at", default=str(selected.get("started_at") or "")): str,
                    vol.Optional("ended_at", default=str(selected.get("ended_at") or "")): str,
                    vol.Optional(ATTR_NOTES, default=str(selected.get("notes") or "")): str,
                    vol.Optional(
                        "status",
                        default=str(selected.get("status") or "completed"),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_selector_options(["active", "completed", "cancelled"]),
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_add_set_to_workout(
        self, user_input: dict | None = None
    ) -> FlowResult:
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        await coordinator.async_refresh_workout_history(notify=False)
        workout_options = [
            {
                "value": str(row.get("workout_id")),
                "label": f"#{row.get('workout_id')} {row.get('started_at')}",
            }
            for row in coordinator.get_recent_workouts()
            if row.get("workout_id") is not None
        ]
        if not workout_options:
            return self.async_abort(reason="workout_history_empty")
        exercise_options = _selector_options_from_rows(
            coordinator.exercise_options_for_options_flow(include_disabled=False)
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                workout_id = int(str(user_input.get("workout_id")))
                exercise_id = str(user_input.get(ATTR_EXERCISE_ID) or "").strip().lower()
                equipment_id = _optional_str(user_input.get(ATTR_EQUIPMENT_ID))
                weight = float(user_input.get(ATTR_WEIGHT, 0))
                reps = int(user_input.get(ATTR_REPS, 0))
                notes = _optional_str(user_input.get(ATTR_NOTES))
                created_raw = _optional_str(user_input.get("created_at"))
                created_at = _parse_datetime_input(created_raw) if created_raw else None
                await coordinator.async_add_set_to_existing_workout(
                    workout_id=workout_id,
                    exercise_id=exercise_id,
                    weight=weight,
                    reps=reps,
                    equipment_id=equipment_id,
                    notes=notes,
                    created_at=created_at,
                )
                return await self.async_step_manage_workouts()
            except Exception:
                _LOGGER.exception("HAGym options flow add_set_to_workout failed")
                errors["base"] = "options_flow_error"
        return self.async_show_form(
            step_id="add_set_to_workout",
            data_schema=vol.Schema(
                {
                    vol.Required("workout_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=workout_options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    ),
                    vol.Required(ATTR_EXERCISE_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=exercise_options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    ),
                    vol.Optional(
                        ATTR_EQUIPMENT_ID,
                        default=str(user_input.get(ATTR_EQUIPMENT_ID, ""))
                        if user_input
                        else "",
                    ): str,
                    vol.Required(ATTR_WEIGHT, default=0): NumberSelector(
                        NumberSelectorConfig(min=0, max=1000, step=0.5, mode="box")
                    ),
                    vol.Required(ATTR_REPS, default=10): NumberSelector(
                        NumberSelectorConfig(min=1, max=999, step=1, mode="box")
                    ),
                    vol.Optional(ATTR_NOTES, default=""): str,
                    vol.Optional("created_at", default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_edit_set_select_workout(
        self, user_input: dict | None = None
    ) -> FlowResult:
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        await coordinator.async_refresh_workout_history(notify=False)
        options = [
            {
                "value": str(row.get("workout_id")),
                "label": f"#{row.get('workout_id')} {row.get('started_at')}",
            }
            for row in coordinator.get_recent_workouts()
            if row.get("workout_id") is not None
        ]
        if not options:
            return self.async_abort(reason="workout_history_empty")
        if user_input is not None:
            raw_workout_id = str(user_input.get("workout_id") or "").strip()
            if not raw_workout_id.isdigit():
                return self.async_abort(reason="workout_not_found")
            self._selected_workout_id = int(raw_workout_id)
            return await self.async_step_edit_set_select_set()
        return self.async_show_form(
            step_id="edit_set_select_workout",
            data_schema=vol.Schema(
                {
                    vol.Required("workout_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )

    async def async_step_edit_set_select_set(
        self, user_input: dict | None = None
    ) -> FlowResult:
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        if self._selected_workout_id is None:
            return await self.async_step_edit_set_select_workout()
        await coordinator.async_refresh_workout_history(notify=False)
        workout = next(
            (
                row
                for row in coordinator.get_recent_workouts()
                if int(row.get("workout_id", -1)) == self._selected_workout_id
            ),
            None,
        )
        if workout is None:
            return self.async_abort(reason="workout_not_found")
        set_options = [
            {
                "value": str(item.get("set_id")),
                "label": f"#{item.get('set_id')} {item.get('exercise_name')} {item.get('weight')}x{item.get('reps')}",
            }
            for item in workout.get("sets", [])
            if item.get("set_id") is not None
        ]
        if not set_options:
            return self.async_abort(reason="set_not_found")
        if user_input is not None:
            raw_set_id = str(user_input.get("set_id") or "").strip()
            if not raw_set_id.isdigit():
                return self.async_abort(reason="set_not_found")
            self._selected_set_id = int(raw_set_id)
            return await self.async_step_edit_set()
        return self.async_show_form(
            step_id="edit_set_select_set",
            data_schema=vol.Schema(
                {
                    vol.Required("set_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=set_options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )

    async def async_step_edit_set(self, user_input: dict | None = None) -> FlowResult:
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        if self._selected_workout_id is None or self._selected_set_id is None:
            return await self.async_step_edit_set_select_workout()
        await coordinator.async_refresh_workout_history(notify=False)
        workout = next(
            (
                row
                for row in coordinator.get_recent_workouts()
                if int(row.get("workout_id", -1)) == self._selected_workout_id
            ),
            None,
        )
        if workout is None:
            return self.async_abort(reason="workout_not_found")
        selected_set = next(
            (
                item
                for item in workout.get("sets", [])
                if int(item.get("set_id", -1)) == self._selected_set_id
            ),
            None,
        )
        if selected_set is None:
            return self.async_abort(reason="set_not_found")
        exercise_options = _selector_options_from_rows(
            coordinator.exercise_options_for_options_flow(include_disabled=True)
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                equipment_id = _optional_str(user_input.get(ATTR_EQUIPMENT_ID))
                exercise_id = str(user_input.get(ATTR_EXERCISE_ID) or "").strip().lower()
                weight = float(user_input.get(ATTR_WEIGHT))
                reps = int(user_input.get(ATTR_REPS))
                notes = _optional_str(user_input.get(ATTR_NOTES))
                created_raw = _optional_str(user_input.get("created_at"))
                created_at = _parse_datetime_input(created_raw) if created_raw else None
                await coordinator.async_update_existing_set(
                    set_id=self._selected_set_id,
                    equipment_id=equipment_id,
                    exercise_id=exercise_id,
                    weight=weight,
                    reps=reps,
                    notes=notes,
                    created_at=created_at,
                )
                return await self.async_step_manage_workouts()
            except Exception:
                _LOGGER.exception("HAGym options flow edit_set failed")
                errors["base"] = "options_flow_error"
        return self.async_show_form(
            step_id="edit_set",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        ATTR_EQUIPMENT_ID,
                        default=str(selected_set.get("equipment_id") or ""),
                    ): str,
                    vol.Required(
                        ATTR_EXERCISE_ID,
                        default=str(selected_set.get("exercise_id") or ""),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=exercise_options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    ),
                    vol.Required(ATTR_WEIGHT, default=float(selected_set.get("weight", 0.0))): NumberSelector(
                        NumberSelectorConfig(min=0, max=1000, step=0.5, mode="box")
                    ),
                    vol.Required(ATTR_REPS, default=int(selected_set.get("reps", 1))): NumberSelector(
                        NumberSelectorConfig(min=1, max=999, step=1, mode="box")
                    ),
                    vol.Optional(ATTR_NOTES, default=str(selected_set.get("notes") or "")): str,
                    vol.Optional("created_at", default=str(selected_set.get("created_at") or "")): str,
                }
            ),
            errors=errors,
        )

    async def async_step_delete_set_select_workout(
        self, user_input: dict | None = None
    ) -> FlowResult:
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        await coordinator.async_refresh_workout_history(notify=False)
        options = [
            {
                "value": str(row.get("workout_id")),
                "label": f"#{row.get('workout_id')} {row.get('started_at')}",
            }
            for row in coordinator.get_recent_workouts()
            if row.get("workout_id") is not None
        ]
        if not options:
            return self.async_abort(reason="workout_history_empty")
        if user_input is not None:
            raw_workout_id = str(user_input.get("workout_id") or "").strip()
            if not raw_workout_id.isdigit():
                return self.async_abort(reason="workout_not_found")
            self._selected_workout_id = int(raw_workout_id)
            return await self.async_step_delete_set_select_set()
        return self.async_show_form(
            step_id="delete_set_select_workout",
            data_schema=vol.Schema(
                {
                    vol.Required("workout_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )

    async def async_step_delete_set_select_set(
        self, user_input: dict | None = None
    ) -> FlowResult:
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        if self._selected_workout_id is None:
            return await self.async_step_delete_set_select_workout()
        await coordinator.async_refresh_workout_history(notify=False)
        workout = next(
            (
                row
                for row in coordinator.get_recent_workouts()
                if int(row.get("workout_id", -1)) == self._selected_workout_id
            ),
            None,
        )
        if workout is None:
            return self.async_abort(reason="workout_not_found")
        options = [
            {
                "value": str(item.get("set_id")),
                "label": f"#{item.get('set_id')} {item.get('exercise_name')} {item.get('weight')}x{item.get('reps')}",
            }
            for item in workout.get("sets", [])
            if item.get("set_id") is not None
        ]
        if not options:
            return self.async_abort(reason="set_not_found")
        if user_input is not None:
            raw_set_id = str(user_input.get("set_id") or "").strip()
            if not raw_set_id.isdigit():
                return self.async_abort(reason="set_not_found")
            self._selected_set_id = int(raw_set_id)
            return await self.async_step_delete_set_confirm()
        return self.async_show_form(
            step_id="delete_set_select_set",
            data_schema=vol.Schema(
                {
                    vol.Required("set_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )

    async def async_step_delete_set_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        if self._selected_set_id is None:
            return await self.async_step_delete_set_select_workout()
        if user_input is not None:
            if bool(user_input.get("confirm_delete", False)):
                try:
                    await coordinator.async_delete_existing_set(self._selected_set_id)
                    return await self.async_step_manage_workouts()
                except Exception:
                    _LOGGER.exception("HAGym options flow delete_set failed")
                    return self.async_abort(reason="options_flow_error")
            return await self.async_step_manage_workouts()
        return self.async_show_form(
            step_id="delete_set_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required("confirm_delete", default=False): bool,
                }
            ),
        )

    async def async_step_delete_workout_select(
        self, user_input: dict | None = None
    ) -> FlowResult:
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        await coordinator.async_refresh_workout_history(notify=False)
        options = [
            {
                "value": str(row.get("workout_id")),
                "label": f"#{row.get('workout_id')} {row.get('started_at')}",
            }
            for row in coordinator.get_recent_workouts()
            if row.get("workout_id") is not None
        ]
        if not options:
            return self.async_abort(reason="workout_history_empty")
        if user_input is not None:
            raw_workout_id = str(user_input.get("workout_id") or "").strip()
            if not raw_workout_id.isdigit():
                return self.async_abort(reason="workout_not_found")
            self._selected_workout_id = int(raw_workout_id)
            return await self.async_step_delete_workout_confirm()
        return self.async_show_form(
            step_id="delete_workout_select",
            data_schema=vol.Schema(
                {
                    vol.Required("workout_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )

    async def async_step_delete_workout_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        if self._selected_workout_id is None:
            return await self.async_step_delete_workout_select()
        if user_input is not None:
            try:
                if bool(user_input.get("confirm_delete", False)):
                    await coordinator.async_delete_existing_workout(
                        self._selected_workout_id, delete_sets=True
                    )
                return await self.async_step_manage_workouts()
            except Exception:
                _LOGGER.exception("HAGym options flow delete_workout failed")
                return self.async_abort(reason="options_flow_error")
        return self.async_show_form(
            step_id="delete_workout_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required("confirm_delete", default=False): bool,
                }
            ),
        )

    async def async_step_configure_household_users(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Configure household user filtering."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_INCLUDED_USER_IDS: user_input.get(CONF_INCLUDED_USER_IDS, []),
                },
            )

        users = []
        if self._coordinator is not None:
            users = self._coordinator.users

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
            step_id="configure_household_users",
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

    async def async_step_add_exercise(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Add a new exercise."""
        errors: dict[str, str] = {}
        coordinator = self._coordinator

        if user_input is not None:
            normalized_exercise_id = _normalize_exercise_id(
                str(user_input.get(ATTR_EXERCISE_ID, ""))
            )
            name_en = str(user_input.get(ATTR_NAME_EN, "")).strip()
            name_de = _optional_str(user_input.get(ATTR_NAME_DE))
            muscle_group = _optional_str(user_input.get(ATTR_MUSCLE_GROUP))
            equipment = _optional_str(user_input.get(ATTR_EQUIPMENT))
            equipment_id = _optional_str(user_input.get(ATTR_EQUIPMENT_ID))
            metric_type = _optional_str(user_input.get(ATTR_METRIC_TYPE))
            enabled = bool(user_input.get(ATTR_ENABLED, True))
            sort_order_raw = user_input.get(ATTR_SORT_ORDER, _DEFAULT_SORT_ORDER)
            sort_order = _coerce_int(sort_order_raw, _DEFAULT_SORT_ORDER)

            # Bodyweight fields (OptionsFlow add_exercise)
            uses_bodyweight = bool(user_input.get(ATTR_USES_BODYWEIGHT, False))
            bodyweight_pct_raw = user_input.get(ATTR_BODYWEIGHT_FACTOR, 100)
            try:
                bodyweight_factor = round(float(bodyweight_pct_raw) / 100.0, 4)
            except (TypeError, ValueError):
                bodyweight_factor = 1.0
            bodyweight_factor = max(0.0, min(1.0, bodyweight_factor))

            if not normalized_exercise_id:
                errors[ATTR_EXERCISE_ID] = "invalid_exercise_id"
            elif coordinator is not None and coordinator.get_exercise(normalized_exercise_id):
                errors[ATTR_EXERCISE_ID] = "exercise_exists"

            if not name_en:
                errors[ATTR_NAME_EN] = "name_required"
            if metric_type is not None and metric_type not in _METRIC_TYPE_OPTIONS:
                errors[ATTR_METRIC_TYPE] = "invalid_metric_type"
            if not _is_valid_sort_order_input(sort_order_raw):
                errors[ATTR_SORT_ORDER] = "invalid_sort_order"

            if coordinator is None:
                errors["base"] = "coordinator_unavailable"

            if not errors and coordinator is not None:
                await coordinator.async_add_exercise(
                    exercise_id=normalized_exercise_id,
                    name_en=name_en,
                    name_de=name_de,
                    muscle_group=muscle_group,
                    equipment=equipment,
                    equipment_id=equipment_id,
                    metric_type=metric_type,
                    enabled=enabled,
                    sort_order=sort_order,
                    uses_bodyweight=uses_bodyweight,
                    bodyweight_factor=bodyweight_factor,
                )
                return await self.async_step_manage_exercises()

        return self.async_show_form(
            step_id="add_exercise",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        ATTR_EXERCISE_ID,
                        default=str(user_input.get(ATTR_EXERCISE_ID, ""))
                        if user_input
                        else "",
                    ): str,
                    vol.Required(
                        ATTR_NAME_EN,
                        default=str(user_input.get(ATTR_NAME_EN, "")) if user_input else "",
                    ): str,
                    vol.Optional(
                        ATTR_NAME_DE,
                        default=str(user_input.get(ATTR_NAME_DE, "")) if user_input else "",
                    ): str,
                    vol.Optional(
                        ATTR_MUSCLE_GROUP,
                        default=str(user_input.get(ATTR_MUSCLE_GROUP, ""))
                        if user_input
                        else "",
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_selector_options(_MUSCLE_GROUP_OPTIONS),
                            mode="dropdown",
                            custom_value=True,
                        )
                    ),
                    vol.Optional(
                        ATTR_EQUIPMENT,
                        default=str(user_input.get(ATTR_EQUIPMENT, "")) if user_input else "",
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_selector_options(_EQUIPMENT_OPTIONS),
                            mode="dropdown",
                            custom_value=True,
                        )
                    ),
                    vol.Optional(
                        ATTR_EQUIPMENT_ID,
                        default=str(user_input.get(ATTR_EQUIPMENT_ID, "")) if user_input else "",
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_selector_options_from_rows(
                                coordinator.get_equipment_options(include_disabled=False)
                            )
                            if coordinator
                            else [],
                            mode="dropdown",
                            custom_value=True,
                        )
                    ),
                    vol.Optional(
                        ATTR_METRIC_TYPE,
                        default=str(user_input.get(ATTR_METRIC_TYPE, METRIC_TYPE_STRENGTH))
                        if user_input
                        else METRIC_TYPE_STRENGTH,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_selector_options(_METRIC_TYPE_OPTIONS),
                            mode="dropdown",
                            custom_value=False,
                        )
                    ),
                    vol.Optional(
                        ATTR_SORT_ORDER,
                        default=user_input.get(ATTR_SORT_ORDER, _DEFAULT_SORT_ORDER)
                        if user_input
                        else _DEFAULT_SORT_ORDER,
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=9999,
                            step=1,
                            mode="box",
                        )
                    ),
                    vol.Optional(
                        ATTR_ENABLED,
                        default=bool(user_input.get(ATTR_ENABLED, True))
                        if user_input
                        else True,
                    ): bool,
                    # Bodyweight support fields (OptionsFlow add_exercise)
                    vol.Optional(
                        ATTR_USES_BODYWEIGHT,
                        default=bool(user_input.get(ATTR_USES_BODYWEIGHT, False))
                        if user_input
                        else False,
                    ): bool,
                    vol.Optional(
                        ATTR_BODYWEIGHT_FACTOR,
                        default=round(float(user_input.get(ATTR_BODYWEIGHT_FACTOR, 100)))
                        if user_input is not None and ATTR_BODYWEIGHT_FACTOR in user_input
                        else 100,
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=1,
                            mode="box",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_edit_exercise_select(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Select one exercise to edit."""
        coordinator = self._coordinator
        options = (
            _selector_options_from_rows(
                coordinator.exercise_options_for_options_flow(include_disabled=True)
            )
            if coordinator is not None
            else []
        )
        if not options:
            return self.async_abort(reason="exercise_catalog_empty")
        if user_input is not None:
            self._selected_exercise_id = str(user_input[ATTR_EXERCISE_ID])
            return await self.async_step_edit_exercise()

        return self.async_show_form(
            step_id="edit_exercise_select",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_EXERCISE_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )

    async def async_step_edit_exercise(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Edit one exercise."""
        errors: dict[str, str] = {}
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")

        exercise_id = self._selected_exercise_id
        if not exercise_id:
            return await self.async_step_edit_exercise_select()

        exercise = coordinator.get_exercise(exercise_id)
        if exercise is None:
            errors["base"] = "exercise_not_found"
            return await self.async_step_edit_exercise_select()

        if user_input is not None:
            name_en = str(user_input.get(ATTR_NAME_EN, "")).strip()
            name_de = _optional_str(user_input.get(ATTR_NAME_DE))
            muscle_group = _optional_str(user_input.get(ATTR_MUSCLE_GROUP))
            equipment = _optional_str(user_input.get(ATTR_EQUIPMENT))
            equipment_id = _optional_str(user_input.get(ATTR_EQUIPMENT_ID))
            metric_type = _optional_str(user_input.get(ATTR_METRIC_TYPE))
            enabled = bool(user_input.get(ATTR_ENABLED, True))
            sort_order_raw = user_input.get(ATTR_SORT_ORDER, exercise.get("sort_order", 0))
            sort_order = _coerce_int(sort_order_raw, int(exercise.get("sort_order", 0)))

            # Bodyweight fields
            uses_bodyweight = bool(user_input.get(ATTR_USES_BODYWEIGHT, False))
            stored_factor_raw = exercise.get(ATTR_BODYWEIGHT_FACTOR)
            stored_factor = 1.0 if stored_factor_raw is None else float(stored_factor_raw)
            if ATTR_BODYWEIGHT_FACTOR in user_input:
                # Formular sendet Prozent (0–100), konvertiere zu Faktor
                bodyweight_pct_raw = user_input[ATTR_BODYWEIGHT_FACTOR]
                try:
                    bodyweight_factor = round(float(bodyweight_pct_raw) / 100.0, 4)
                except (TypeError, ValueError):
                    bodyweight_factor = stored_factor
            else:
                # Feld nicht im Formular — behalte den gespeicherten Faktor unverändert
                bodyweight_factor = stored_factor
            # Clamp to [0.0, 1.0]
            bodyweight_factor = max(0.0, min(1.0, bodyweight_factor))

            if not name_en:
                errors[ATTR_NAME_EN] = "name_required"
            if metric_type is not None and metric_type not in _METRIC_TYPE_OPTIONS:
                errors[ATTR_METRIC_TYPE] = "invalid_metric_type"
            if not _is_valid_sort_order_input(sort_order_raw):
                errors[ATTR_SORT_ORDER] = "invalid_sort_order"

            if not errors:
                await coordinator.async_update_exercise(
                    exercise_id=exercise_id,
                    name_en=name_en,
                    name_de=name_de,
                    muscle_group=muscle_group,
                    equipment=equipment,
                    equipment_id=equipment_id,
                    metric_type=metric_type,
                    enabled=enabled,
                    sort_order=sort_order,
                    uses_bodyweight=uses_bodyweight,
                    bodyweight_factor=bodyweight_factor,
                )
                return await self.async_step_manage_exercises()

        return self.async_show_form(
            step_id="edit_exercise",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        ATTR_NAME_EN,
                        default=str(
                            user_input.get(ATTR_NAME_EN, exercise.get(ATTR_NAME_EN, ""))
                        )
                        if user_input
                        else str(exercise.get(ATTR_NAME_EN, "")),
                    ): str,
                    vol.Optional(
                        ATTR_NAME_DE,
                        default=str(
                            user_input.get(ATTR_NAME_DE, exercise.get(ATTR_NAME_DE, ""))
                        )
                        if user_input
                        else str(exercise.get(ATTR_NAME_DE, "")),
                    ): str,
                    vol.Optional(
                        ATTR_MUSCLE_GROUP,
                        default=str(
                            user_input.get(
                                ATTR_MUSCLE_GROUP, exercise.get(ATTR_MUSCLE_GROUP, "")
                            )
                        )
                        if user_input
                        else str(exercise.get(ATTR_MUSCLE_GROUP, "")),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_selector_options(_MUSCLE_GROUP_OPTIONS),
                            mode="dropdown",
                            custom_value=True,
                        )
                    ),
                    vol.Optional(
                        ATTR_EQUIPMENT,
                        default=str(
                            user_input.get(ATTR_EQUIPMENT, exercise.get(ATTR_EQUIPMENT, ""))
                        )
                        if user_input
                        else str(exercise.get(ATTR_EQUIPMENT, "")),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_selector_options(_EQUIPMENT_OPTIONS),
                            mode="dropdown",
                            custom_value=True,
                        )
                    ),
                    vol.Optional(
                        ATTR_EQUIPMENT_ID,
                        default=str(
                            user_input.get(ATTR_EQUIPMENT_ID, exercise.get(ATTR_EQUIPMENT_ID, ""))
                        )
                        if user_input
                        else str(exercise.get(ATTR_EQUIPMENT_ID, "")),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_selector_options_from_rows(
                                coordinator.get_equipment_options(include_disabled=False)
                            ),
                            mode="dropdown",
                            custom_value=True,
                        )
                    ),
                    vol.Optional(
                        ATTR_METRIC_TYPE,
                        default=str(
                            user_input.get(
                                ATTR_METRIC_TYPE,
                                exercise.get(ATTR_METRIC_TYPE, METRIC_TYPE_STRENGTH),
                            )
                        )
                        if user_input
                        else str(exercise.get(ATTR_METRIC_TYPE, METRIC_TYPE_STRENGTH)),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_selector_options(_METRIC_TYPE_OPTIONS),
                            mode="dropdown",
                            custom_value=False,
                        )
                    ),
                    vol.Optional(
                        ATTR_SORT_ORDER,
                        default=user_input.get(
                            ATTR_SORT_ORDER, int(exercise.get(ATTR_SORT_ORDER, 0))
                        )
                        if user_input
                        else int(exercise.get(ATTR_SORT_ORDER, 0)),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=9999,
                            step=1,
                            mode="box",
                        )
                    ),
                    vol.Optional(
                        ATTR_ENABLED,
                        default=bool(user_input.get(ATTR_ENABLED, True))
                        if user_input
                        else bool(exercise.get(ATTR_ENABLED, 1)),
                    ): bool,
                    # Bodyweight support fields
                    vol.Optional(
                        ATTR_USES_BODYWEIGHT,
                        default=bool(user_input.get(ATTR_USES_BODYWEIGHT, False))
                        if user_input
                        else bool(int(exercise.get(ATTR_USES_BODYWEIGHT, 0) or 0)),
                    ): bool,
                    vol.Optional(
                        ATTR_BODYWEIGHT_FACTOR,
                        default=int(round(user_input[ATTR_BODYWEIGHT_FACTOR]))
                        if user_input is not None and ATTR_BODYWEIGHT_FACTOR in user_input
                        else _bodyweight_factor_to_percent(exercise),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=1,
                            mode="box",
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"exercise_id": exercise_id},
        )

    async def async_step_toggle_exercise_select(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Select one exercise for disable/enable toggle."""
        coordinator = self._coordinator
        options = (
            _selector_options_from_rows(
                coordinator.exercise_options_for_options_flow(include_disabled=True)
            )
            if coordinator is not None
            else []
        )
        if not options:
            return self.async_abort(reason="exercise_catalog_empty")
        if user_input is not None:
            self._selected_exercise_id = str(user_input[ATTR_EXERCISE_ID])
            return await self.async_step_toggle_exercise_confirm()

        return self.async_show_form(
            step_id="toggle_exercise_select",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_EXERCISE_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )

    async def async_step_toggle_exercise_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Toggle one exercise between enabled and disabled."""
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")

        exercise_id = self._selected_exercise_id
        if not exercise_id:
            return await self.async_step_toggle_exercise_select()

        exercise = coordinator.get_exercise(exercise_id)
        if exercise is None:
            return self.async_abort(reason="exercise_not_found")

        is_enabled = int(exercise.get("enabled", 1)) == 1
        if user_input is not None and bool(user_input.get("confirm", True)):
            if is_enabled:
                await coordinator.async_disable_exercise(exercise_id)
            else:
                await coordinator.async_update_exercise(exercise_id=exercise_id, enabled=True)
            return await self.async_step_manage_exercises()

        action = "disable" if is_enabled else "enable"
        status = "enabled" if is_enabled else "disabled"
        return self.async_show_form(
            step_id="toggle_exercise_confirm",
            data_schema=vol.Schema({vol.Required("confirm", default=True): bool}),
            description_placeholders={
                "exercise_id": exercise_id,
                "exercise_name": coordinator.exercise_display_name(exercise_id),
                "status": status,
                "action": action,
            },
        )

    async def async_step_add_equipment(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Add one equipment entry."""
        errors: dict[str, str] = {}
        coordinator = self._coordinator

        if user_input is not None:
            equipment_id = _normalize_equipment_id(str(user_input.get(ATTR_EQUIPMENT_ID, "")))
            name_de = str(user_input.get(ATTR_NAME_DE, "")).strip()
            name_en = _optional_str(user_input.get(ATTR_NAME_EN))
            description = _optional_str(user_input.get(ATTR_DESCRIPTION))
            icon = _optional_str(user_input.get(ATTR_ICON))
            location = _optional_str(user_input.get(ATTR_LOCATION))
            enabled = bool(user_input.get(ATTR_ENABLED, True))
            sort_order_raw = user_input.get(ATTR_SORT_ORDER, _DEFAULT_SORT_ORDER)
            sort_order = _coerce_int(sort_order_raw, _DEFAULT_SORT_ORDER)

            if not equipment_id:
                errors[ATTR_EQUIPMENT_ID] = "invalid_equipment_id"
            elif coordinator is not None and coordinator.get_equipment(equipment_id):
                errors[ATTR_EQUIPMENT_ID] = "equipment_exists"
            if not name_de:
                errors[ATTR_NAME_DE] = "name_required"
            if not _is_valid_sort_order_input(sort_order_raw):
                errors[ATTR_SORT_ORDER] = "invalid_sort_order"
            if coordinator is None:
                errors["base"] = "coordinator_unavailable"

            if not errors and coordinator is not None and equipment_id is not None:
                await coordinator.async_add_equipment(
                    equipment_id=equipment_id,
                    name=name_de,
                    name_en=name_en or name_de,
                    name_de=name_de,
                    description=description,
                    icon=icon,
                    location=location,
                    enabled=enabled,
                    sort_order=sort_order,
                )
                return await self.async_step_manage_equipment()

        return self.async_show_form(
            step_id="add_equipment",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        ATTR_EQUIPMENT_ID,
                        default=str(user_input.get(ATTR_EQUIPMENT_ID, "")) if user_input else "",
                    ): str,
                    vol.Required(
                        ATTR_NAME_DE,
                        default=str(user_input.get(ATTR_NAME_DE, "")) if user_input else "",
                    ): str,
                    vol.Optional(
                        ATTR_NAME_EN,
                        default=str(user_input.get(ATTR_NAME_EN, "")) if user_input else "",
                    ): str,
                    vol.Optional(
                        ATTR_DESCRIPTION,
                        default=str(user_input.get(ATTR_DESCRIPTION, "")) if user_input else "",
                    ): str,
                    vol.Optional(ATTR_ICON, default=str(user_input.get(ATTR_ICON, "")) if user_input else ""): str,
                    vol.Optional(
                        ATTR_LOCATION,
                        default=str(user_input.get(ATTR_LOCATION, "")) if user_input else "",
                    ): str,
                    vol.Optional(
                        ATTR_SORT_ORDER,
                        default=user_input.get(ATTR_SORT_ORDER, _DEFAULT_SORT_ORDER)
                        if user_input
                        else _DEFAULT_SORT_ORDER,
                    ): NumberSelector(
                        NumberSelectorConfig(min=0, max=9999, step=1, mode="box")
                    ),
                    vol.Optional(
                        ATTR_ENABLED,
                        default=bool(user_input.get(ATTR_ENABLED, True)) if user_input else True,
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_edit_equipment_select(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Select one equipment for edit."""
        coordinator = self._coordinator
        options = (
            _selector_options_from_rows(coordinator.get_equipment_options(include_disabled=True))
            if coordinator
            else []
        )
        if not options:
            return self.async_abort(reason="equipment_catalog_empty")
        if user_input is not None:
            self._selected_equipment_id = str(user_input[ATTR_EQUIPMENT_ID])
            return await self.async_step_edit_equipment()

        return self.async_show_form(
            step_id="edit_equipment_select",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_EQUIPMENT_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )

    async def async_step_edit_equipment(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Edit selected equipment."""
        errors: dict[str, str] = {}
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        equipment_id = self._selected_equipment_id
        if not equipment_id:
            return await self.async_step_edit_equipment_select()
        equipment = coordinator.get_equipment(equipment_id)
        if equipment is None:
            return self.async_abort(reason="equipment_not_found")

        if user_input is not None:
            name_de = str(user_input.get(ATTR_NAME_DE, "")).strip()
            name_en = _optional_str(user_input.get(ATTR_NAME_EN))
            description = _optional_str(user_input.get(ATTR_DESCRIPTION))
            icon = _optional_str(user_input.get(ATTR_ICON))
            location = _optional_str(user_input.get(ATTR_LOCATION))
            enabled = bool(user_input.get(ATTR_ENABLED, True))
            sort_order_raw = user_input.get(ATTR_SORT_ORDER, equipment.get(ATTR_SORT_ORDER, 100))
            sort_order = _coerce_int(sort_order_raw, int(equipment.get(ATTR_SORT_ORDER, 100)))
            if not name_de:
                errors[ATTR_NAME_DE] = "name_required"
            if not _is_valid_sort_order_input(sort_order_raw):
                errors[ATTR_SORT_ORDER] = "invalid_sort_order"
            if not errors:
                await coordinator.async_update_equipment(
                    equipment_id=equipment_id,
                    name=name_de,
                    name_en=name_en or name_de,
                    name_de=name_de,
                    description=description,
                    icon=icon,
                    location=location,
                    enabled=enabled,
                    sort_order=sort_order,
                )
                return await self.async_step_manage_equipment()

        return self.async_show_form(
            step_id="edit_equipment",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        ATTR_NAME_DE,
                        default=str(
                            user_input.get(
                                ATTR_NAME_DE,
                                equipment.get(ATTR_NAME_DE, equipment.get("name", "")),
                            )
                        )
                        if user_input
                        else str(equipment.get(ATTR_NAME_DE, equipment.get("name", ""))),
                    ): str,
                    vol.Optional(
                        ATTR_NAME_EN,
                        default=str(
                            user_input.get(
                                ATTR_NAME_EN,
                                equipment.get(ATTR_NAME_EN, equipment.get(ATTR_NAME_DE, "")),
                            )
                        )
                        if user_input
                        else str(
                            equipment.get(
                                ATTR_NAME_EN, equipment.get(ATTR_NAME_DE, equipment.get("name", ""))
                            )
                        ),
                    ): str,
                    vol.Optional(
                        ATTR_DESCRIPTION,
                        default=str(
                            user_input.get(ATTR_DESCRIPTION, equipment.get(ATTR_DESCRIPTION, ""))
                        )
                        if user_input
                        else str(equipment.get(ATTR_DESCRIPTION, "")),
                    ): str,
                    vol.Optional(
                        ATTR_ICON,
                        default=str(user_input.get(ATTR_ICON, equipment.get(ATTR_ICON, "")))
                        if user_input
                        else str(equipment.get(ATTR_ICON, "")),
                    ): str,
                    vol.Optional(
                        ATTR_LOCATION,
                        default=str(user_input.get(ATTR_LOCATION, equipment.get(ATTR_LOCATION, "")))
                        if user_input
                        else str(equipment.get(ATTR_LOCATION, "")),
                    ): str,
                    vol.Optional(
                        ATTR_SORT_ORDER,
                        default=user_input.get(
                            ATTR_SORT_ORDER, int(equipment.get(ATTR_SORT_ORDER, 100))
                        )
                        if user_input
                        else int(equipment.get(ATTR_SORT_ORDER, 100)),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0, max=9999, step=1, mode="box")
                    ),
                    vol.Optional(
                        ATTR_ENABLED,
                        default=bool(user_input.get(ATTR_ENABLED, True))
                        if user_input
                        else bool(equipment.get(ATTR_ENABLED, 1)),
                    ): bool,
                }
            ),
            errors=errors,
            description_placeholders={"equipment_id": equipment_id},
        )

    async def async_step_toggle_equipment_select(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Select one equipment for enable/disable toggle."""
        coordinator = self._coordinator
        options = (
            _selector_options_from_rows(coordinator.get_equipment_options(include_disabled=True))
            if coordinator
            else []
        )
        if not options:
            return self.async_abort(reason="equipment_catalog_empty")
        if user_input is not None:
            self._selected_equipment_id = str(user_input[ATTR_EQUIPMENT_ID])
            return await self.async_step_toggle_equipment_confirm()

        return self.async_show_form(
            step_id="toggle_equipment_select",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_EQUIPMENT_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )

    async def async_step_toggle_equipment_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Toggle selected equipment enabled state."""
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        equipment_id = self._selected_equipment_id
        if not equipment_id:
            return await self.async_step_toggle_equipment_select()
        equipment = coordinator.get_equipment(equipment_id)
        if equipment is None:
            return self.async_abort(reason="equipment_not_found")

        is_enabled = int(equipment.get("enabled", 1)) == 1
        if user_input is not None and bool(user_input.get("confirm", True)):
            if is_enabled:
                await coordinator.async_disable_equipment(equipment_id)
            else:
                await coordinator.async_update_equipment(equipment_id=equipment_id, enabled=True)
            return await self.async_step_manage_equipment()

        return self.async_show_form(
            step_id="toggle_equipment_confirm",
            data_schema=vol.Schema({vol.Required("confirm", default=True): bool}),
            description_placeholders={
                "equipment_id": equipment_id,
                "equipment_name": coordinator.equipment_display_name(equipment_id),
                "status": "enabled" if is_enabled else "disabled",
                "action": "disable" if is_enabled else "enable",
            },
        )

    async def async_step_assign_exercises_select_equipment(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Select equipment for exercise assignment."""
        coordinator = self._coordinator
        options = (
            _selector_options_from_rows(coordinator.get_equipment_options(include_disabled=False))
            if coordinator
            else []
        )
        if not options:
            return self.async_abort(reason="equipment_catalog_empty")
        if user_input is not None:
            self._selected_equipment_id = str(user_input[ATTR_EQUIPMENT_ID])
            return await self.async_step_assign_exercises_select_exercises()

        return self.async_show_form(
            step_id="assign_exercises_select_equipment",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_EQUIPMENT_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )

    async def async_step_assign_exercises_select_exercises(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Multi-select exercises and assign to selected equipment."""
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        equipment_id = self._selected_equipment_id
        if not equipment_id:
            return await self.async_step_assign_exercises_select_equipment()
        if coordinator.get_equipment(equipment_id) is None:
            return self.async_abort(reason="equipment_not_found")

        options = _selector_options_from_rows(
            coordinator.exercise_options_for_options_flow(include_disabled=True)
        )
        defaults = [
            str(row.get("id"))
            for row in coordinator.get_exercises_for_equipment(equipment_id)
            if row.get("id")
        ]
        if user_input is not None:
            selected = [str(item) for item in user_input.get(ATTR_EXERCISE_ID, [])]
            all_rows = _selector_options_from_rows(
                coordinator.exercise_options_for_options_flow(include_disabled=True)
            )
            all_ids = [str(row["value"]) for row in all_rows]
            for exercise_id in all_ids:
                if exercise_id in selected:
                    await coordinator.async_assign_exercise_to_equipment(exercise_id, equipment_id)
                elif coordinator.get_equipment_for_exercise(exercise_id) == equipment_id:
                    await coordinator.async_assign_exercise_to_equipment(exercise_id, None)
            return await self.async_step_manage_equipment()

        return self.async_show_form(
            step_id="assign_exercises_select_exercises",
            data_schema=vol.Schema(
                {
                    vol.Optional(ATTR_EXERCISE_ID, default=defaults): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
            description_placeholders={"equipment_id": equipment_id},
        )

    async def async_step_add_muscle_group(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Add one muscle group entry."""
        errors: dict[str, str] = {}
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")

        if user_input is not None:
            muscle_group_id = _normalize_muscle_group_id(
                str(user_input.get(ATTR_MUSCLE_GROUP_ID, ""))
            )
            name_en = str(user_input.get(ATTR_NAME_EN, "")).strip()
            name_de = _optional_str(user_input.get(ATTR_NAME_DE))
            description = _optional_str(user_input.get(ATTR_DESCRIPTION))
            icon = _optional_str(user_input.get(ATTR_ICON))
            body_region = _optional_str(user_input.get(ATTR_BODY_REGION))
            enabled = bool(user_input.get(ATTR_ENABLED, True))
            sort_order_raw = user_input.get(ATTR_SORT_ORDER, _DEFAULT_SORT_ORDER)
            sort_order = _coerce_int(sort_order_raw, _DEFAULT_SORT_ORDER)

            if not muscle_group_id:
                errors[ATTR_MUSCLE_GROUP_ID] = "invalid_muscle_group_id"
            elif coordinator.get_muscle_group(muscle_group_id):
                errors[ATTR_MUSCLE_GROUP_ID] = "muscle_group_exists"
            if not name_en:
                errors[ATTR_NAME_EN] = "name_required"
            if not _is_valid_sort_order_input(sort_order_raw):
                errors[ATTR_SORT_ORDER] = "invalid_sort_order"

            if not errors and muscle_group_id is not None:
                try:
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
                except Exception:
                    _LOGGER.exception("HAGym options flow add_muscle_group failed")
                    return self.async_abort(reason="options_flow_error")
                return await self.async_step_manage_muscle_groups()

        return self.async_show_form(
            step_id="add_muscle_group",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        ATTR_MUSCLE_GROUP_ID,
                        default=str(user_input.get(ATTR_MUSCLE_GROUP_ID, ""))
                        if user_input
                        else "",
                    ): str,
                    vol.Required(
                        ATTR_NAME_EN,
                        default=str(user_input.get(ATTR_NAME_EN, ""))
                        if user_input
                        else "",
                    ): str,
                    vol.Optional(
                        ATTR_NAME_DE,
                        default=str(user_input.get(ATTR_NAME_DE, "")) if user_input else "",
                    ): str,
                    vol.Optional(
                        ATTR_DESCRIPTION,
                        default=str(user_input.get(ATTR_DESCRIPTION, ""))
                        if user_input
                        else "",
                    ): str,
                    vol.Optional(
                        ATTR_ICON,
                        default=str(user_input.get(ATTR_ICON, "mdi:arm-flex"))
                        if user_input
                        else "mdi:arm-flex",
                    ): str,
                    vol.Optional(
                        ATTR_BODY_REGION,
                        default=str(user_input.get(ATTR_BODY_REGION, ""))
                        if user_input
                        else "",
                    ): str,
                    vol.Optional(
                        ATTR_SORT_ORDER,
                        default=user_input.get(ATTR_SORT_ORDER, _DEFAULT_SORT_ORDER)
                        if user_input
                        else _DEFAULT_SORT_ORDER,
                    ): NumberSelector(
                        NumberSelectorConfig(min=0, max=9999, step=1, mode="box")
                    ),
                    vol.Optional(
                        ATTR_ENABLED,
                        default=bool(user_input.get(ATTR_ENABLED, True))
                        if user_input
                        else True,
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_edit_muscle_group_select(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Select one muscle group to edit."""
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        options = coordinator.muscle_group_options_for_options_flow(include_disabled=True)
        if not options:
            return self.async_abort(reason="muscle_group_catalog_empty")
        if user_input is not None:
            self._selected_muscle_group_id = str(user_input[ATTR_MUSCLE_GROUP_ID])
            return await self.async_step_edit_muscle_group()
        return self.async_show_form(
            step_id="edit_muscle_group_select",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_MUSCLE_GROUP_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )

    async def async_step_edit_muscle_group(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Edit one muscle group."""
        errors: dict[str, str] = {}
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")

        muscle_group_id = self._selected_muscle_group_id
        if not muscle_group_id:
            return await self.async_step_edit_muscle_group_select()
        muscle_group = coordinator.get_muscle_group(muscle_group_id)
        if muscle_group is None:
            return self.async_abort(reason="muscle_group_not_found")

        if user_input is not None:
            name_en = str(user_input.get(ATTR_NAME_EN, "")).strip()
            name_de = _optional_str(user_input.get(ATTR_NAME_DE))
            description = _optional_str(user_input.get(ATTR_DESCRIPTION))
            icon = _optional_str(user_input.get(ATTR_ICON))
            body_region = _optional_str(user_input.get(ATTR_BODY_REGION))
            enabled = bool(user_input.get(ATTR_ENABLED, True))
            sort_order_raw = user_input.get(
                ATTR_SORT_ORDER, int(muscle_group.get(ATTR_SORT_ORDER, 100))
            )
            sort_order = _coerce_int(
                sort_order_raw, int(muscle_group.get(ATTR_SORT_ORDER, 100))
            )
            if not name_en:
                errors[ATTR_NAME_EN] = "name_required"
            if not _is_valid_sort_order_input(sort_order_raw):
                errors[ATTR_SORT_ORDER] = "invalid_sort_order"
            if not errors:
                try:
                    await coordinator.async_update_muscle_group(
                        muscle_group_id=muscle_group_id,
                        name_en=name_en,
                        name_de=name_de,
                        description=description,
                        icon=icon,
                        body_region=body_region,
                        enabled=enabled,
                        sort_order=sort_order,
                    )
                except Exception:
                    _LOGGER.exception("HAGym options flow edit_muscle_group failed")
                    return self.async_abort(reason="options_flow_error")
                return await self.async_step_manage_muscle_groups()

        return self.async_show_form(
            step_id="edit_muscle_group",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        ATTR_NAME_EN,
                        default=str(
                            user_input.get(ATTR_NAME_EN, muscle_group.get(ATTR_NAME_EN, ""))
                        )
                        if user_input
                        else str(muscle_group.get(ATTR_NAME_EN, "")),
                    ): str,
                    vol.Optional(
                        ATTR_NAME_DE,
                        default=str(
                            user_input.get(ATTR_NAME_DE, muscle_group.get(ATTR_NAME_DE, ""))
                        )
                        if user_input
                        else str(muscle_group.get(ATTR_NAME_DE, "")),
                    ): str,
                    vol.Optional(
                        ATTR_DESCRIPTION,
                        default=str(
                            user_input.get(
                                ATTR_DESCRIPTION, muscle_group.get(ATTR_DESCRIPTION, "")
                            )
                        )
                        if user_input
                        else str(muscle_group.get(ATTR_DESCRIPTION, "")),
                    ): str,
                    vol.Optional(
                        ATTR_ICON,
                        default=str(user_input.get(ATTR_ICON, muscle_group.get(ATTR_ICON, "")))
                        if user_input
                        else str(muscle_group.get(ATTR_ICON, "")),
                    ): str,
                    vol.Optional(
                        ATTR_BODY_REGION,
                        default=str(
                            user_input.get(
                                ATTR_BODY_REGION, muscle_group.get(ATTR_BODY_REGION, "")
                            )
                        )
                        if user_input
                        else str(muscle_group.get(ATTR_BODY_REGION, "")),
                    ): str,
                    vol.Optional(
                        ATTR_SORT_ORDER,
                        default=user_input.get(
                            ATTR_SORT_ORDER, int(muscle_group.get(ATTR_SORT_ORDER, 100))
                        )
                        if user_input
                        else int(muscle_group.get(ATTR_SORT_ORDER, 100)),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0, max=9999, step=1, mode="box")
                    ),
                    vol.Optional(
                        ATTR_ENABLED,
                        default=bool(user_input.get(ATTR_ENABLED, True))
                        if user_input
                        else bool(muscle_group.get(ATTR_ENABLED, 1)),
                    ): bool,
                }
            ),
            errors=errors,
            description_placeholders={"muscle_group_id": muscle_group_id},
        )

    async def async_step_toggle_muscle_group_select(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Select one muscle group for disable/enable toggle."""
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        options = coordinator.muscle_group_options_for_options_flow(include_disabled=True)
        if not options:
            return self.async_abort(reason="muscle_group_catalog_empty")
        if user_input is not None:
            self._selected_muscle_group_id = str(user_input[ATTR_MUSCLE_GROUP_ID])
            return await self.async_step_toggle_muscle_group_confirm()
        return self.async_show_form(
            step_id="toggle_muscle_group_select",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_MUSCLE_GROUP_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )

    async def async_step_toggle_muscle_group_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Toggle one muscle group between enabled and disabled."""
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")

        muscle_group_id = self._selected_muscle_group_id
        if not muscle_group_id:
            return await self.async_step_toggle_muscle_group_select()
        muscle_group = coordinator.get_muscle_group(muscle_group_id)
        if muscle_group is None:
            return self.async_abort(reason="muscle_group_not_found")

        is_enabled = int(muscle_group.get("enabled", 1)) == 1
        if user_input is not None and bool(user_input.get("confirm", True)):
            try:
                if is_enabled:
                    await coordinator.async_disable_muscle_group(muscle_group_id)
                else:
                    await coordinator.async_update_muscle_group(
                        muscle_group_id=muscle_group_id, enabled=True
                    )
            except Exception:
                _LOGGER.exception("HAGym options flow toggle_muscle_group failed")
                return self.async_abort(reason="options_flow_error")
            return await self.async_step_manage_muscle_groups()

        action = "disable" if is_enabled else "enable"
        status = "enabled" if is_enabled else "disabled"
        return self.async_show_form(
            step_id="toggle_muscle_group_confirm",
            data_schema=vol.Schema({vol.Required("confirm", default=True): bool}),
            description_placeholders={
                "muscle_group_id": muscle_group_id,
                "muscle_group_name": coordinator.muscle_group_display_name(muscle_group_id),
                "status": status,
                "action": action,
            },
        )

    async def async_step_assign_muscle_groups_select_exercise(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Select one exercise for muscle-group assignment."""
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        options = _selector_options_from_rows(
            coordinator.exercise_options_for_options_flow(include_disabled=True)
        )
        if not options:
            return self.async_abort(reason="exercise_catalog_empty")
        if user_input is not None:
            selected_exercise_id = str(user_input.get(ATTR_EXERCISE_ID) or "").strip()
            if not selected_exercise_id:
                return self.async_abort(reason="exercise_not_found")
            self._assign_muscle_exercise_id = selected_exercise_id
            try:
                rows = await coordinator.async_get_muscle_groups_for_exercise(
                    self._assign_muscle_exercise_id
                )
            except Exception:
                _LOGGER.exception(
                    "HAGym options flow assign_muscle_groups_select_exercise failed"
                )
                return self.async_abort(reason="options_flow_error")
            self._assign_primary_muscle_group_ids = [
                str(row.get("muscle_group_id"))
                for row in rows
                if str(row.get("role") or "") == "primary" and row.get("muscle_group_id")
            ]
            self._assign_secondary_muscle_group_ids = [
                str(row.get("muscle_group_id"))
                for row in rows
                if str(row.get("role") or "") == "secondary" and row.get("muscle_group_id")
            ]
            self._assign_stabilizer_muscle_group_ids = [
                str(row.get("muscle_group_id"))
                for row in rows
                if str(row.get("role") or "") == "stabilizer"
                and row.get("muscle_group_id")
            ]
            return await self.async_step_assign_muscle_groups_select_primary()
        return self.async_show_form(
            step_id="assign_muscle_groups_select_exercise",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_EXERCISE_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=False,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
        )

    async def async_step_assign_muscle_groups_select_primary(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Select primary muscle groups for selected exercise."""
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        if not self._assign_muscle_exercise_id:
            return await self.async_step_assign_muscle_groups_select_exercise()
        options = coordinator.muscle_group_options_for_options_flow(include_disabled=False)
        if not options:
            return self.async_abort(reason="muscle_group_catalog_empty")
        defaults = self._assign_primary_muscle_group_ids
        if user_input is not None:
            self._assign_primary_muscle_group_ids = [
                str(item) for item in user_input.get(ATTR_MUSCLE_GROUP_ID, [])
            ]
            return await self.async_step_assign_muscle_groups_select_secondary()
        return self.async_show_form(
            step_id="assign_muscle_groups_select_primary",
            data_schema=vol.Schema(
                {
                    vol.Optional(ATTR_MUSCLE_GROUP_ID, default=defaults): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
            description_placeholders={"exercise_id": self._assign_muscle_exercise_id},
        )

    async def async_step_assign_muscle_groups_select_secondary(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Select secondary muscle groups for selected exercise."""
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        if not self._assign_muscle_exercise_id:
            return await self.async_step_assign_muscle_groups_select_exercise()
        options = coordinator.muscle_group_options_for_options_flow(include_disabled=False)
        if not options:
            return self.async_abort(reason="muscle_group_catalog_empty")
        defaults = self._assign_secondary_muscle_group_ids
        if user_input is not None:
            self._assign_secondary_muscle_group_ids = [
                str(item) for item in user_input.get(ATTR_MUSCLE_GROUP_ID, [])
            ]
            return await self.async_step_assign_muscle_groups_select_stabilizer()
        return self.async_show_form(
            step_id="assign_muscle_groups_select_secondary",
            data_schema=vol.Schema(
                {
                    vol.Optional(ATTR_MUSCLE_GROUP_ID, default=defaults): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
            description_placeholders={"exercise_id": self._assign_muscle_exercise_id},
        )

    async def async_step_assign_muscle_groups_select_stabilizer(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Select stabilizer muscle groups and proceed to weight assignment."""
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        if not self._assign_muscle_exercise_id:
            return await self.async_step_assign_muscle_groups_select_exercise()
        options = coordinator.muscle_group_options_for_options_flow(include_disabled=False)
        if not options:
            return self.async_abort(reason="muscle_group_catalog_empty")
        defaults = self._assign_stabilizer_muscle_group_ids
        if user_input is not None:
            stabilizer_ids = [str(item) for item in user_input.get(ATTR_MUSCLE_GROUP_ID, [])]
            await self._compute_normalized_weight_defaults(
                coordinator,
                self._assign_primary_muscle_group_ids,
                self._assign_secondary_muscle_group_ids,
                stabilizer_ids,
            )
            return await self.async_step_assign_muscle_groups_set_weights()
        return self.async_show_form(
            step_id="assign_muscle_groups_select_stabilizer",
            data_schema=vol.Schema(
                {
                    vol.Optional(ATTR_MUSCLE_GROUP_ID, default=defaults): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            custom_value=False,
                            mode="dropdown",
                        )
                    )
                }
            ),
            description_placeholders={"exercise_id": self._assign_muscle_exercise_id},
        )


    # ---- Normalized muscle-group weighting helpers ----

    async def _compute_normalized_weight_defaults(
        self,
        coordinator: Any,
        primary_ids: list[str],
        secondary_ids: list[str],
        stabilizer_ids: list[str],
    ) -> None:
        """Compute pre-filled normalized weight factors for the selected muscle groups.

        If existing mappings have non-zero weights, normalize proportionally.
        Otherwise use role-based defaults (primary 60%, secondary 30%, stabilizer 10%).
        """
        all_ids = primary_ids + secondary_ids + stabilizer_ids
        if not all_ids:
            self._assign_weight_factors = {}
            return

        # Try to load existing weight factors from DB for proportional normalization
        try:
            rows = await coordinator.async_get_muscle_groups_for_exercise(  # type: ignore[attr-defined]
                self._assign_muscle_exercise_id,
            )
        except Exception:
            rows = []

        existing_factors: dict[str, float] = {}
        for row in rows or []:
            mg_id = str(row.get("muscle_group_id") or "")
            wf = float(row.get("weight_factor", 0.0))
            if mg_id and wf > 0:
                existing_factors[mg_id] = wf

        total_existing = sum(existing_factors.values())

        self._assign_weight_factors: dict[str, float] = {}
        role_map: dict[str, str] = {}
        for mg in primary_ids:
            role_map[mg] = "primary"
        for mg in secondary_ids:
            role_map[mg] = "secondary"
        for mg in stabilizer_ids:
            role_map[mg] = "stabilizer"

        if total_existing > 0.01 and existing_factors:
            # Proportional normalization from existing factors (for IDs that still exist)
            raw: dict[str, float] = {}
            for mg_id in all_ids:
                raw[mg_id] = existing_factors.get(mg_id, 0.5)
            total_raw = sum(raw.values())
            if total_raw > 0:
                self._assign_weight_factors = {k: round(v / total_raw, 4) for k, v in raw.items()}
        else:
            # Role-based defaults: primary=60%, secondary=30%, stabilizer=10%
            counts: dict[str, int] = {"primary": 0, "secondary": 0, "stabilizer": 0}
            for role in role_map.values():
                counts[role] += 1

            shares: dict[str, float] = {
                "primary": 0.6, "secondary": 0.3, "stabilizer": 0.1,
            }
            active_roles = [r for r in counts if counts[r] > 0]
            inactive_share = sum(
                shares.get(r, 0)
                for r in ("primary", "secondary", "stabilizer")
                if r not in active_roles
            )
            active_total = sum(shares.get(r, 0) for r in active_roles) or 1.0

            redistributed_shares: dict[str, float] = {}
            for r in active_roles:
                base_share = shares.get(r, 0.0)
                if len(active_roles) > 1 and inactive_share > 0:
                    redistributed_shares[r] = round(
                        base_share + (inactive_share * base_share / active_total), 4
                    )
                else:
                    redistributed_shares[r] = shares.get(r, 0.0)

            # Normalize so sum == 1.0 exactly
            redist_total = sum(redistributed_shares.values()) or 1.0
            if abs(redist_total - 1.0) > 0.001:
                for r in active_roles:
                    redistributed_shares[r] /= redist_total

            self._assign_weight_factors = {}
            last_in_role: dict[str, str | None] = {
                "primary": None, "secondary": None, "stabilizer": None,
            }
            for mg_id in all_ids:
                role = role_map.get(mg_id, "primary")
                if counts[role] > 0:
                    last_in_role[role] = mg_id

            for mg_id in all_ids:
                role = role_map.get(mg_id, "primary")
                share = redistributed_shares.get(role, 0.3)
                n = counts[role] or 1
                if n > 1 and last_in_role[role] == mg_id:
                    base_per_item = round(share / (n - 1), 4) if n > 2 else share
                    remainder = round(share - base_per_item * (n - 1), 4)
                    self._assign_weight_factors[mg_id] = max(remainder, 0.0)
                elif n > 0:
                    self._assign_weight_factors[mg_id] = round(share / n, 4)

    def _build_weight_schema(self) -> vol.Schema:
        """Build a dynamic schema with integer fields for each selected muscle group."""
        coordinator = self._coordinator
        mg_display: dict[str, str] = {}
        for mg_id in self._assign_weight_factors:
            display_name = mg_id
            if coordinator is not None:
                row = coordinator.get_muscle_group(mg_id)  # type: ignore[attr-defined]
                if row:
                    name_de = row.get("name_de") or ""
                    name_en = row.get("name_en") or mg_id
                    display_name = str(name_de or name_en)
            mg_display[mg_id] = display_name

        schema_fields: dict[vol.Optional, type] = {}  # type: ignore[type-arg]
        for mg_id in self._assign_weight_factors:
            pct_default = round(self._assign_weight_factors.get(mg_id, 0.5) * 100)
            label_key = f"weight_{mg_id}"
            schema_fields[vol.Optional(label_key, default=pct_default)] = int

        return vol.Schema(schema_fields)

    async def _validate_and_save_muscle_group_weights(
        self, coordinator: Any, user_input: dict[str, Any]
    ) -> FlowResult | None:
        """Validate weight inputs and save. Returns a FlowResult on error (re-show form), else None."""
        errors: dict[str, str] = {}

        all_ids = list(self._assign_weight_factors.keys())
        if not all_ids:
            errors["base"] = "muscle_group_mapping_empty"
            return self.async_show_form(
                step_id="assign_muscle_groups_set_weights",
                data_schema=self._build_weight_schema(),
                errors=errors,
                description_placeholders={"exercise_id": self._assign_muscle_exercise_id},
            )

        parsed: dict[str, float] = {}
        for mg_id in all_ids:
            raw_val = user_input.get(f"weight_{mg_id}", 50)
            try:
                pct = float(raw_val)
            except (TypeError, ValueError):
                errors[f"weight_{mg_id}"] = "invalid_weight_value"
                continue
            if pct < 0 or pct > 100:
                errors[f"weight_{mg_id}"] = "invalid_weight_range"
                continue
            parsed[mg_id] = round(pct / 100.0, 4)

        if errors:
            return self.async_show_form(
                step_id="assign_muscle_groups_set_weights",
                data_schema=self._build_weight_schema(),
                errors=errors,
                description_placeholders={"exercise_id": self._assign_muscle_exercise_id},
            )

        total = round(sum(parsed.values()), 4)
        if abs(total - 1.0) > 0.001:
            errors["base"] = "muscle_group_weights_sum"
            return self.async_show_form(
                step_id="assign_muscle_groups_set_weights",
                data_schema=self._build_weight_schema(),
                errors=errors,
                description_placeholders={"exercise_id": self._assign_muscle_exercise_id},
            )

        try:
            mappings = []
            for mg_id in all_ids:
                if mg_id in self._assign_primary_muscle_group_ids:
                    role = "primary"
                elif mg_id in self._assign_secondary_muscle_group_ids:
                    role = "secondary"
                else:
                    role = "stabilizer"
                mappings.append({
                    "muscle_group_id": mg_id,
                    "role": role,
                    "weight_factor": parsed[mg_id],
                })
            await coordinator.async_replace_muscle_groups_with_weights(  # type: ignore[attr-defined]
                exercise_id=self._assign_muscle_exercise_id,
                mappings=mappings,
            )
        except ValueError as exc:
            _LOGGER.warning("HAGym muscle group weight validation failed: %s", exc)
            errors["base"] = str(exc.args[0]) if exc.args else "muscle_group_weights_sum"
            return self.async_show_form(
                step_id="assign_muscle_groups_set_weights",
                data_schema=self._build_weight_schema(),
                errors=errors,
            )
        except Exception:
            _LOGGER.exception("HAGym options flow assign_muscle_groups_set_weights failed")
            return self.async_abort(reason="options_flow_error")
        return None

    async def async_step_assign_muscle_groups_set_weights(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Set normalized weight factors for each selected muscle group."""
        coordinator = self._coordinator
        if coordinator is None:
            return self.async_abort(reason="coordinator_unavailable")
        if not self._assign_muscle_exercise_id:
            return await self.async_step_assign_muscle_groups_select_exercise()

        errors: dict[str, str] | None = None
        if user_input is not None:
            result = await self._validate_and_save_muscle_group_weights(
                coordinator, user_input
            )
            if result is not None:
                return result
            return await self.async_step_manage_muscle_groups()

        schema = self._build_weight_schema()
        return self.async_show_form(
            step_id="assign_muscle_groups_set_weights",
            data_schema=schema,
            errors=errors,
            description_placeholders={"exercise_id": self._assign_muscle_exercise_id},
        )



def _optional_str(value: Any) -> str | None:
    """Return stripped string value or None for non-strings/empty strings."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _normalize_exercise_id(raw_exercise_id: str) -> str | None:
    """Normalize raw exercise id to lowercase underscore format and validate it."""
    normalized = raw_exercise_id.strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return None
    if not _EXERCISE_ID_PATTERN.match(normalized):
        return None
    return normalized


def _normalize_equipment_id(raw_equipment_id: str) -> str | None:
    """Normalize raw equipment id and validate allowed characters."""
    normalized = raw_equipment_id.strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return None
    if not _EQUIPMENT_ID_PATTERN.match(normalized):
        return None
    return normalized


def _normalize_muscle_group_id(raw_muscle_group_id: str) -> str | None:
    """Normalize raw muscle group id and validate allowed characters."""
    normalized = raw_muscle_group_id.strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return None
    if not _MUSCLE_GROUP_ID_PATTERN.match(normalized):
        return None
    return normalized


def _coerce_int(value: Any, fallback: int) -> int:
    """Convert a value to int, returning fallback for unsupported/invalid values."""
    if isinstance(value, bool):
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _is_valid_sort_order_input(value: Any) -> bool:
    """Validate that sort order input represents a whole number (not bool)."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return value.is_integer()
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return False
    return parsed.is_integer()


def _selector_options(values: list[str]) -> list[dict[str, str]]:
    """Convert plain values into explicit selector option dictionaries."""
    options: list[dict[str, str]] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized:
            continue
        options.append({"value": normalized, "label": normalized})
    return options


def _selector_options_from_rows(rows: list[dict[str, str]] | None) -> list[dict[str, str]]:
    """Normalize selector options to Home Assistant SelectSelector option dicts."""
    if not rows:
        return []
    options: list[dict[str, str]] = []
    for row in rows:
        value = str(row.get("value") or "").strip()
        if not value:
            continue
        label = str(row.get("label") or value).strip() or value
        options.append({"value": value, "label": label})
    return options


def _parse_datetime_input(raw_value: str) -> datetime:
    normalized = str(raw_value).strip()
    if not normalized:
        raise ValueError("Datetime must not be empty")
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
