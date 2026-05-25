"""Config flow for HA Fitness Tracker."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    ATTR_ENABLED,
    ATTR_EQUIPMENT,
    ATTR_EXERCISE_ID,
    ATTR_MUSCLE_GROUP,
    ATTR_NAME_DE,
    ATTR_NAME_EN,
    ATTR_SORT_ORDER,
    CONF_DISPLAY_NAME,
    CONF_INCLUDED_USER_IDS,
    DEFAULT_DISPLAY_NAME,
    DOMAIN,
)

_EXERCISE_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
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
    """Options flow for household users and exercise management."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._selected_exercise_id: str | None = None

    @property
    def _coordinator(self):
        return self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Show options root menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "configure_household_users",
                "manage_exercises",
                "add_exercise",
                "edit_exercise_select",
                "toggle_exercise_select",
            ],
        )

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
                "init",
            ],
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
            enabled = bool(user_input.get(ATTR_ENABLED, True))
            sort_order_raw = user_input.get(ATTR_SORT_ORDER, _DEFAULT_SORT_ORDER)
            sort_order = _coerce_int(sort_order_raw, _DEFAULT_SORT_ORDER)

            if not normalized_exercise_id:
                errors[ATTR_EXERCISE_ID] = "invalid_exercise_id"
            elif coordinator is not None and coordinator.get_exercise(normalized_exercise_id):
                errors[ATTR_EXERCISE_ID] = "exercise_exists"

            if not name_en:
                errors[ATTR_NAME_EN] = "name_required"
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
                    enabled=enabled,
                    sort_order=sort_order,
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
                            options=_MUSCLE_GROUP_OPTIONS,
                            mode="dropdown",
                            custom_value=True,
                        )
                    ),
                    vol.Optional(
                        ATTR_EQUIPMENT,
                        default=str(user_input.get(ATTR_EQUIPMENT, "")) if user_input else "",
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_EQUIPMENT_OPTIONS,
                            mode="dropdown",
                            custom_value=True,
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
            coordinator.exercise_options_for_options_flow(include_disabled=True)
            if coordinator is not None
            else []
        )
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
            enabled = bool(user_input.get(ATTR_ENABLED, True))
            sort_order_raw = user_input.get(ATTR_SORT_ORDER, exercise.get("sort_order", 0))
            sort_order = _coerce_int(sort_order_raw, int(exercise.get("sort_order", 0)))

            if not name_en:
                errors[ATTR_NAME_EN] = "name_required"
            if not _is_valid_sort_order_input(sort_order_raw):
                errors[ATTR_SORT_ORDER] = "invalid_sort_order"

            if not errors:
                await coordinator.async_update_exercise(
                    exercise_id=exercise_id,
                    name_en=name_en,
                    name_de=name_de,
                    muscle_group=muscle_group,
                    equipment=equipment,
                    enabled=enabled,
                    sort_order=sort_order,
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
                            options=_MUSCLE_GROUP_OPTIONS,
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
                            options=_EQUIPMENT_OPTIONS,
                            mode="dropdown",
                            custom_value=True,
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
            coordinator.exercise_options_for_options_flow(include_disabled=True)
            if coordinator is not None
            else []
        )
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


def _optional_str(value: Any) -> str | None:
    """Return stripped string value or None for non-strings/empty strings."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _normalize_exercise_id(raw_exercise_id: str) -> str | None:
    """Normalize raw exercise id to lowercase underscore format and validate it."""
    normalized = raw_exercise_id.strip().lower().replace("-", "_")
    if not normalized:
        return None
    if not _EXERCISE_ID_PATTERN.match(normalized):
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
