"""Config flow for HAGym."""
from __future__ import annotations

import logging
import re
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
    ATTR_ENABLED,
    ATTR_DESCRIPTION,
    ATTR_EQUIPMENT,
    ATTR_EQUIPMENT_ID,
    ATTR_EXERCISE_ID,
    ATTR_ICON,
    ATTR_LOCATION,
    ATTR_MUSCLE_GROUP,
    ATTR_MUSCLE_GROUP_ID,
    ATTR_NAME_DE,
    ATTR_NAME_EN,
    ATTR_BODY_REGION,
    ATTR_SORT_ORDER,
    CONF_DISPLAY_NAME,
    CONF_INCLUDED_USER_IDS,
    DEFAULT_DISPLAY_NAME,
    DOMAIN,
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
                name = str(user_input.get("name", "")).strip()
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
                if not name:
                    errors["name"] = "name_required"
                if not _is_valid_sort_order_input(sort_order_raw):
                    errors[ATTR_SORT_ORDER] = "invalid_sort_order"

                if not errors:
                    if coordinator is not None:
                        await coordinator.async_add_equipment(
                            equipment_id=equipment_id,
                            name=name,
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
                            name=name,
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
                        "name",
                        default=str(user_input.get("name", "")) if user_input else "",
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
                enabled = bool(user_input.get(ATTR_ENABLED, True))
                sort_order_raw = user_input.get(ATTR_SORT_ORDER, _DEFAULT_SORT_ORDER)
                sort_order = _coerce_int(sort_order_raw, _DEFAULT_SORT_ORDER)

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
                            enabled=enabled,
                            sort_order=sort_order,
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
                            enabled=enabled,
                            sort_order=sort_order,
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "HAFitnessOptionsFlow":
        """Return options flow for HAGym."""
        return HAFitnessOptionsFlow()


class HAFitnessOptionsFlow(config_entries.OptionsFlow):
    """Options flow for household users and exercise management."""

    def __init__(self) -> None:
        self._selected_exercise_id: str | None = None
        self._selected_equipment_id: str | None = None
        self._selected_muscle_group_id: str | None = None
        self._assign_muscle_exercise_id: str | None = None
        self._assign_primary_muscle_group_ids: list[str] = []
        self._assign_secondary_muscle_group_ids: list[str] = []
        self._assign_stabilizer_muscle_group_ids: list[str] = []

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
            equipment_id = _optional_str(user_input.get(ATTR_EQUIPMENT_ID))
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
                    equipment_id=equipment_id,
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
                    equipment_id=equipment_id,
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
            name = str(user_input.get("name", "")).strip()
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
            if not name:
                errors["name"] = "name_required"
            if not _is_valid_sort_order_input(sort_order_raw):
                errors[ATTR_SORT_ORDER] = "invalid_sort_order"
            if coordinator is None:
                errors["base"] = "coordinator_unavailable"

            if not errors and coordinator is not None and equipment_id is not None:
                await coordinator.async_add_equipment(
                    equipment_id=equipment_id,
                    name=name,
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
                    vol.Required("name", default=str(user_input.get("name", "")) if user_input else ""): str,
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
            name = str(user_input.get("name", "")).strip()
            description = _optional_str(user_input.get(ATTR_DESCRIPTION))
            icon = _optional_str(user_input.get(ATTR_ICON))
            location = _optional_str(user_input.get(ATTR_LOCATION))
            enabled = bool(user_input.get(ATTR_ENABLED, True))
            sort_order_raw = user_input.get(ATTR_SORT_ORDER, equipment.get(ATTR_SORT_ORDER, 100))
            sort_order = _coerce_int(sort_order_raw, int(equipment.get(ATTR_SORT_ORDER, 100)))
            if not name:
                errors["name"] = "name_required"
            if not _is_valid_sort_order_input(sort_order_raw):
                errors[ATTR_SORT_ORDER] = "invalid_sort_order"
            if not errors:
                await coordinator.async_update_equipment(
                    equipment_id=equipment_id,
                    name=name,
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
                        "name",
                        default=str(user_input.get("name", equipment.get("name", "")))
                        if user_input
                        else str(equipment.get("name", "")),
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
                "equipment_name": str(equipment.get("name") or equipment_id),
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
        """Select stabilizer muscle groups and save exercise assignments."""
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
            try:
                await coordinator.async_replace_muscle_groups_for_exercise(
                    exercise_id=self._assign_muscle_exercise_id,
                    primary_ids=self._assign_primary_muscle_group_ids,
                    secondary_ids=self._assign_secondary_muscle_group_ids,
                    stabilizer_ids=stabilizer_ids,
                )
            except Exception:
                _LOGGER.exception(
                    "HAGym options flow assign_muscle_groups_select_stabilizer failed"
                )
                return self.async_abort(reason="options_flow_error")
            return await self.async_step_manage_muscle_groups()
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
