"""HA Fitness Tracker coordinator."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
import sqlite3
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import EXERCISE_IDS, LEGACY_USER_ID, STATE_ACTIVE, STATE_READY
from .storage import HAFitnessStore

_LOGGER = logging.getLogger(__name__)


class HAFitnessCoordinator:
    """Manages runtime state for the HA Fitness integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        display_name: str,
        store: HAFitnessStore,
        included_user_ids: list[str] | None = None,
    ) -> None:
        self.hass = hass
        self.display_name = display_name
        self._store = store
        self._included_user_ids = included_user_ids

        self._current_workout_id: int | None = None
        self._current_workout_started_at: str | None = None
        self._current_workout_user_id: str | None = None
        self._workout_state: str = STATE_READY
        self._active_exercise_id: str | None = None
        self._weight: float = 0.0
        self._reps: int = 0
        self._notes: str = ""
        self._current_set_number: int = 0
        self._last_set_summary: str | None = None
        self._last_saved_set: dict[str, Any] | None = None
        self._total_volume: float = 0.0
        self._total_sets: int = 0
        self._total_workouts: int = 0
        self._recent_sets: list[dict[str, Any]] = []
        self._exercises: list[dict[str, Any]] = []
        self._exercise_by_id: dict[str, dict[str, Any]] = {}
        self._exercise_display_to_id: dict[str, str] = {}
        self._exercise_options: list[str] = []
        self._active_equipment_id: str | None = None
        self._equipment: list[dict[str, Any]] = []
        self._equipment_by_id: dict[str, dict[str, Any]] = {}
        self._equipment_display_to_id: dict[str, str] = {}
        self._equipment_options: list[str] = []
        self._equipment_statistics: list[dict[str, Any]] = []
        self._equipment_statistics_by_id: dict[str, dict[str, Any]] = {}
        self._equipment_runtime_state: dict[str, dict[str, Any]] = {}
        self._locale: str = str(hass.config.language or "en")

        self._pr_by_exercise: dict[str, float] = {exercise_id: 0.0 for exercise_id in EXERCISE_IDS}
        self._volume_by_exercise: dict[str, float] = {
            exercise_id: 0.0 for exercise_id in EXERCISE_IDS
        }

        self._current_user_id: str | None = None
        self._selected_user_id: str | None = None
        self._users: list[dict[str, Any]] = []
        self._personal_total_volume: float = 0.0
        self._personal_total_sets: int = 0
        self._personal_total_workouts: int = 0
        self._personal_recent_sets: list[dict[str, Any]] = []
        self._personal_pr_by_exercise: dict[str, float] = {
            exercise_id: 0.0 for exercise_id in EXERCISE_IDS
        }
        self._personal_volume_by_exercise: dict[str, float] = {
            exercise_id: 0.0 for exercise_id in EXERCISE_IDS
        }

        self._household_total_volume: float = 0.0
        self._household_total_sets: int = 0
        self._household_total_workouts: int = 0
        self._household_recent_sets: list[dict[str, Any]] = []
        self._household_pr_by_exercise: dict[str, float] = {
            exercise_id: 0.0 for exercise_id in EXERCISE_IDS
        }
        self._household_volume_by_exercise: dict[str, float] = {
            exercise_id: 0.0 for exercise_id in EXERCISE_IDS
        }
        self._exercise_statistics: list[dict[str, Any]] = []
        self._listeners: list[Callable[[], None]] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_workout_id(self) -> int | None:
        return self._current_workout_id

    @property
    def current_workout_started_at(self) -> str | None:
        return self._current_workout_started_at

    @property
    def workout_state(self) -> str:
        return self._workout_state

    @property
    def active_exercise(self) -> str | None:
        return self._active_exercise_id

    @property
    def active_exercise_display(self) -> str | None:
        if self._active_exercise_id is None:
            return None
        return self.exercise_display_name(self._active_exercise_id)

    @property
    def weight(self) -> float:
        return self._weight

    @property
    def reps(self) -> int:
        return self._reps

    @property
    def notes(self) -> str:
        return self._notes

    @property
    def current_set_number(self) -> int:
        return self._current_set_number

    @property
    def last_set_summary(self) -> str | None:
        return self._last_set_summary

    @property
    def last_saved_set(self) -> dict[str, Any] | None:
        return self._last_saved_set

    @property
    def total_volume(self) -> float:
        return self._total_volume

    @property
    def total_sets(self) -> int:
        return self._total_sets

    @property
    def total_workouts(self) -> int:
        return self._total_workouts

    @property
    def recent_sets(self) -> list[dict[str, Any]]:
        return self._recent_sets

    @property
    def current_user_id(self) -> str | None:
        return self._current_user_id

    @property
    def selected_user_id(self) -> str | None:
        return self._selected_user_id

    @property
    def users(self) -> list[dict[str, Any]]:
        return self._users

    @property
    def exercises(self) -> list[dict[str, Any]]:
        return self._exercises

    @property
    def exercise_options(self) -> list[str]:
        return self._exercise_options

    @property
    def active_equipment(self) -> str | None:
        return self._active_equipment_id

    @property
    def active_equipment_display(self) -> str | None:
        if self._active_equipment_id is None:
            return "All Equipment"
        row = self._equipment_by_id.get(self._active_equipment_id)
        if row is None:
            return None
        return str(row.get("name") or self._active_equipment_id)

    @property
    def equipment_options(self) -> list[str]:
        return self._equipment_options

    @property
    def equipment(self) -> list[dict[str, Any]]:
        return self._equipment

    @property
    def included_user_ids(self) -> list[str] | None:
        return self._included_user_ids

    @property
    def exercise_statistics(self) -> list[dict[str, Any]]:
        return self._exercise_statistics

    @property
    def equipment_statistics(self) -> list[dict[str, Any]]:
        return self._equipment_statistics

    @property
    def enabled_equipment_ids(self) -> list[str]:
        rows = [
            row
            for row in self._equipment
            if row.get("id") is not None and int(row.get("enabled", 1)) == 1
        ]
        rows.sort(
            key=lambda row: (
                int(row.get("sort_order", 100)),
                str(row.get("name") or row.get("id") or ""),
                str(row.get("id") or ""),
            )
        )
        return [str(row["id"]) for row in rows]

    @property
    def personal_total_volume(self) -> float:
        return self._personal_total_volume

    @property
    def personal_total_sets(self) -> int:
        return self._personal_total_sets

    @property
    def personal_total_workouts(self) -> int:
        return self._personal_total_workouts

    @property
    def personal_recent_sets(self) -> list[dict[str, Any]]:
        return self._personal_recent_sets

    @property
    def household_total_volume(self) -> float:
        return self._household_total_volume

    @property
    def household_total_sets(self) -> int:
        return self._household_total_sets

    @property
    def household_total_workouts(self) -> int:
        return self._household_total_workouts

    @property
    def household_recent_sets(self) -> list[dict[str, Any]]:
        return self._household_recent_sets

    def get_pr_by_exercise(self, exercise: str) -> float:
        return self._pr_by_exercise.get(exercise, 0.0)

    def get_volume_by_exercise(self, exercise: str) -> float:
        return self._volume_by_exercise.get(exercise, 0.0)

    def get_personal_pr_by_exercise(self, exercise: str) -> float:
        return self._personal_pr_by_exercise.get(exercise, 0.0)

    def get_personal_volume_by_exercise(self, exercise: str) -> float:
        return self._personal_volume_by_exercise.get(exercise, 0.0)

    def get_household_pr_by_exercise(self, exercise: str) -> float:
        return self._household_pr_by_exercise.get(exercise, 0.0)

    def get_household_volume_by_exercise(self, exercise: str) -> float:
        return self._household_volume_by_exercise.get(exercise, 0.0)

    # ------------------------------------------------------------------
    # Listener management
    # ------------------------------------------------------------------

    @callback
    def async_add_listener(
        self, update_callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Register a listener and return an unsubscribe callback."""
        self._listeners.append(update_callback)

        def remove_listener() -> None:
            self._listeners.remove(update_callback)

        return remove_listener

    def _notify_listeners(self) -> None:
        for listener in list(self._listeners):
            listener()

    # ------------------------------------------------------------------
    # Setters (called by entities)
    # ------------------------------------------------------------------

    def set_active_exercise(self, exercise_id: str) -> None:
        """Update the currently selected exercise by stable id."""
        if exercise_id not in self._exercise_by_id:
            _LOGGER.warning("HA Fitness: unknown exercise_id '%s' ignored", exercise_id)
            return
        self._active_exercise_id = exercise_id
        if self._active_equipment_id is not None:
            state = self._ensure_equipment_runtime_state(self._active_equipment_id)
            state["active_exercise_id"] = exercise_id
        _LOGGER.debug("HA Fitness: active exercise set to %s", exercise_id)
        self._notify_listeners()

    def set_active_exercise_option(self, option: str) -> None:
        """Set active exercise using localized select option label."""
        exercise_id = self._exercise_display_to_id.get(option)
        if exercise_id is None:
            _LOGGER.warning("HA Fitness: unknown exercise option '%s' ignored", option)
            return
        self._active_exercise_id = exercise_id
        if self._active_equipment_id is not None:
            state = self._ensure_equipment_runtime_state(self._active_equipment_id)
            state["active_exercise_id"] = exercise_id
        _LOGGER.debug("HA Fitness: active exercise option set to %s -> %s", option, exercise_id)
        self._notify_listeners()

    def set_active_equipment(self, equipment_id: str | None) -> None:
        """Update currently selected equipment id (None means no filter)."""
        if equipment_id is not None:
            row = self._equipment_by_id.get(equipment_id)
            if row is None:
                _LOGGER.warning("HA Fitness: unknown equipment_id '%s' ignored", equipment_id)
                return
            if int(row.get("enabled", 1)) != 1:
                _LOGGER.warning("HA Fitness: disabled equipment_id '%s' ignored", equipment_id)
                return
        self._active_equipment_id = equipment_id
        self._rebuild_exercise_options()
        self._sync_global_runtime_from_active_equipment()
        self._notify_listeners()

    def set_active_equipment_option(self, option: str) -> None:
        """Set active equipment from select option label."""
        if option == "All Equipment":
            self.set_active_equipment(None)
            return
        equipment_id = self._equipment_display_to_id.get(option)
        if equipment_id is None:
            _LOGGER.warning("HA Fitness: unknown equipment option '%s' ignored", option)
            return
        self.set_active_equipment(equipment_id)

    def set_weight(self, weight: float) -> None:
        """Update the current weight value."""
        self._weight = weight
        if self._active_equipment_id is not None:
            state = self._ensure_equipment_runtime_state(self._active_equipment_id)
            state["weight"] = float(weight)
        _LOGGER.debug("HA Fitness: weight set to %s", weight)
        self._notify_listeners()

    def set_reps(self, reps: int) -> None:
        """Update the current reps value."""
        self._reps = reps
        if self._active_equipment_id is not None:
            state = self._ensure_equipment_runtime_state(self._active_equipment_id)
            state["reps"] = int(reps)
        _LOGGER.debug("HA Fitness: reps set to %s", reps)
        self._notify_listeners()

    def set_notes(self, notes: str) -> None:
        """Update the current notes value."""
        self._notes = notes
        if self._active_equipment_id is not None:
            state = self._ensure_equipment_runtime_state(self._active_equipment_id)
            state["notes"] = notes
        _LOGGER.debug("HA Fitness: notes updated")
        self._notify_listeners()

    def equipment_display_name(self, equipment_id: str) -> str:
        """Return configured equipment display name or fallback to equipment_id."""
        row = self._equipment_by_id.get(equipment_id)
        if row is None:
            return equipment_id
        return str(row.get("name") or equipment_id)

    def equipment_location(self, equipment_id: str) -> str | None:
        """Return equipment location if configured."""
        row = self._equipment_by_id.get(equipment_id)
        if row is None:
            return None
        location = row.get("location")
        if not isinstance(location, str):
            return None
        stripped = location.strip()
        return stripped if stripped else None

    def equipment_enabled(self, equipment_id: str) -> bool:
        """Return enabled state for equipment id."""
        row = self._equipment_by_id.get(equipment_id)
        if row is None:
            return False
        return int(row.get("enabled", 1)) == 1

    def get_equipment_exercise_options(self, equipment_id: str) -> list[str]:
        """Return localized exercise options assigned to one equipment id."""
        options: list[str] = []
        for row in self.get_exercises_for_equipment(equipment_id):
            exercise_id = str(row.get("id") or "")
            if not exercise_id:
                continue
            options.append(self.exercise_display_name(exercise_id))
        return options

    def get_equipment_active_exercise_id(self, equipment_id: str) -> str | None:
        """Return active exercise id for one equipment runtime state."""
        return self._ensure_equipment_runtime_state(equipment_id).get("active_exercise_id")

    def get_equipment_active_exercise_display(self, equipment_id: str) -> str | None:
        """Return localized active exercise label for one equipment."""
        exercise_id = self.get_equipment_active_exercise_id(equipment_id)
        if exercise_id is None:
            return None
        return self.exercise_display_name(str(exercise_id))

    def set_equipment_active_exercise(self, equipment_id: str, exercise_id: str) -> None:
        """Set active exercise id for one equipment."""
        valid_ids = {
            str(row.get("id") or "")
            for row in self.get_exercises_for_equipment(equipment_id)
            if row.get("id")
        }
        if exercise_id not in valid_ids:
            _LOGGER.warning(
                "HA Fitness: invalid equipment exercise assignment '%s' for equipment '%s'",
                exercise_id,
                equipment_id,
            )
            return
        state = self._ensure_equipment_runtime_state(equipment_id)
        state["active_exercise_id"] = exercise_id
        if equipment_id == self._active_equipment_id:
            self._active_exercise_id = exercise_id
        self._notify_listeners()

    def set_equipment_active_exercise_option(self, equipment_id: str, option: str) -> None:
        """Set active exercise by localized option label for one equipment."""
        for row in self.get_exercises_for_equipment(equipment_id):
            exercise_id = str(row.get("id") or "")
            if not exercise_id:
                continue
            if self.exercise_display_name(exercise_id) == option:
                self.set_equipment_active_exercise(equipment_id, exercise_id)
                return
        _LOGGER.warning(
            "HA Fitness: unknown equipment exercise option '%s' for equipment '%s'",
            option,
            equipment_id,
        )

    def get_equipment_weight(self, equipment_id: str) -> float:
        """Return weight input for one equipment."""
        return float(self._ensure_equipment_runtime_state(equipment_id).get("weight", 0.0))

    def set_equipment_weight(self, equipment_id: str, weight: float) -> None:
        """Set weight input for one equipment."""
        state = self._ensure_equipment_runtime_state(equipment_id)
        state["weight"] = float(weight)
        if equipment_id == self._active_equipment_id:
            self._weight = float(weight)
        self._notify_listeners()

    def get_equipment_reps(self, equipment_id: str) -> int:
        """Return reps input for one equipment."""
        return int(self._ensure_equipment_runtime_state(equipment_id).get("reps", 0))

    def set_equipment_reps(self, equipment_id: str, reps: int) -> None:
        """Set reps input for one equipment."""
        state = self._ensure_equipment_runtime_state(equipment_id)
        state["reps"] = int(reps)
        if equipment_id == self._active_equipment_id:
            self._reps = int(reps)
        self._notify_listeners()

    def get_equipment_notes(self, equipment_id: str) -> str:
        """Return notes input for one equipment."""
        return str(self._ensure_equipment_runtime_state(equipment_id).get("notes", ""))

    def set_equipment_notes(self, equipment_id: str, notes: str) -> None:
        """Set notes input for one equipment."""
        state = self._ensure_equipment_runtime_state(equipment_id)
        state["notes"] = notes
        if equipment_id == self._active_equipment_id:
            self._notes = notes
        self._notify_listeners()

    def get_equipment_last_set_summary(self, equipment_id: str) -> str | None:
        """Return last set summary for one equipment runtime state."""
        state = self._ensure_equipment_runtime_state(equipment_id)
        value = state.get("last_set_summary")
        if isinstance(value, str):
            return value
        return None

    def get_equipment_total_volume(self, equipment_id: str) -> float:
        """Return global total volume for one equipment."""
        row = self._equipment_statistics_by_id.get(equipment_id, {})
        return float(row.get("total_volume", 0.0))

    def get_equipment_total_sets(self, equipment_id: str) -> int:
        """Return global total sets for one equipment."""
        row = self._equipment_statistics_by_id.get(equipment_id, {})
        return int(row.get("total_sets", 0))

    def get_equipment_personal_volume(self, equipment_id: str) -> float:
        """Return personal total volume for one equipment."""
        row = self._equipment_statistics_by_id.get(equipment_id, {})
        return float(row.get("personal_volume", 0.0))

    def get_equipment_household_volume(self, equipment_id: str) -> float:
        """Return household total volume for one equipment."""
        row = self._equipment_statistics_by_id.get(equipment_id, {})
        return float(row.get("household_volume", 0.0))

    async def set_selected_user(self, user_id: str | None) -> None:
        """Set selected user for personal dashboard statistics."""
        if user_id:
            resolved = await self.resolve_user_id(user_id)
            self._selected_user_id = resolved
        else:
            self._selected_user_id = None
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()

    async def async_refresh_exercises(self, notify: bool = True) -> None:
        """Refresh exercise catalog and localized select options from storage."""
        try:
            rows = await self._store.async_get_exercises(enabled_only=False)
        except sqlite3.Error as err:
            _LOGGER.exception("HA Fitness: failed to refresh exercises")
            raise HomeAssistantError("Failed to refresh exercises") from err

        self._exercises = rows
        self._exercise_by_id = {
            str(row["id"]): row for row in rows if row.get("id") is not None
        }
        self._rebuild_exercise_options()
        if notify:
            self._notify_listeners()

    async def async_refresh_equipment(self, notify: bool = True) -> None:
        """Refresh equipment catalog and options from storage."""
        try:
            rows = await self._store.async_get_all_equipment()
        except sqlite3.Error as err:
            _LOGGER.exception("HA Fitness: failed to refresh equipment")
            raise HomeAssistantError("Failed to refresh equipment") from err

        self._equipment = rows
        self._equipment_by_id = {
            str(row["id"]): row for row in rows if row.get("id") is not None
        }
        enabled_rows = [row for row in rows if int(row.get("enabled", 1)) == 1]
        enabled_rows.sort(
            key=lambda row: (
                int(row.get("sort_order", 100)),
                str(row.get("name") or row.get("id") or ""),
                str(row.get("id") or ""),
            )
        )
        self._equipment_display_to_id = {}
        options = ["All Equipment"]
        for row in enabled_rows:
            equipment_id = str(row["id"])
            display = str(row.get("name") or equipment_id)
            options.append(display)
            self._equipment_display_to_id[display] = equipment_id
        self._equipment_options = options
        self._rebuild_equipment_runtime_state()

        if self._active_equipment_id not in self._equipment_by_id:
            self._active_equipment_id = None
        self._rebuild_exercise_options()

        if notify:
            self._notify_listeners()

    async def async_add_exercise(
        self,
        exercise_id: str,
        name_en: str,
        name_de: str | None = None,
        muscle_group: str | None = None,
        equipment: str | None = None,
        equipment_id: str | None = None,
        enabled: bool = True,
        sort_order: int = 0,
    ) -> None:
        """Add one exercise and refresh runtime exercise/stat caches."""
        await self._store.async_add_exercise(
            exercise_id=exercise_id,
            name_en=name_en,
            name_de=name_de,
            muscle_group=muscle_group,
            equipment=equipment,
            equipment_id=equipment_id,
            enabled=enabled,
            sort_order=sort_order,
        )
        await self.async_refresh_exercises(notify=False)
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()

    async def async_update_exercise(
        self,
        exercise_id: str,
        name_en: str | None = None,
        name_de: str | None = None,
        muscle_group: str | None = None,
        equipment: str | None = None,
        equipment_id: str | None = None,
        enabled: bool | None = None,
        sort_order: int | None = None,
    ) -> bool:
        """Update one exercise and refresh runtime caches if changed."""
        updated = await self._store.async_update_exercise(
            exercise_id=exercise_id,
            name_en=name_en,
            name_de=name_de,
            muscle_group=muscle_group,
            equipment=equipment,
            equipment_id=equipment_id,
            enabled=enabled,
            sort_order=sort_order,
        )
        if updated:
            await self.async_refresh_exercises(notify=False)
            await self.async_refresh_statistics(notify=False)
            self._notify_listeners()
        return updated

    async def async_disable_exercise(self, exercise_id: str) -> bool:
        """Disable one exercise and refresh runtime caches if changed."""
        updated = await self._store.async_disable_exercise(exercise_id)
        if updated:
            await self.async_refresh_exercises(notify=False)
            await self.async_refresh_statistics(notify=False)
            self._notify_listeners()
        return updated

    async def async_reload_exercise_catalog(self) -> None:
        """Re-seed defaults and refresh runtime exercise/stat caches."""
        await self._store.async_refresh_exercises()
        await self.async_refresh_exercises(notify=False)
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()

    async def async_add_equipment(
        self,
        equipment_id: str,
        name: str,
        description: str | None = None,
        icon: str | None = None,
        location: str | None = None,
        enabled: bool = True,
        sort_order: int = 100,
    ) -> None:
        """Add equipment and refresh runtime caches."""
        await self._store.async_add_equipment(
            equipment_id=equipment_id,
            name=name,
            description=description,
            icon=icon,
            location=location,
            enabled=enabled,
            sort_order=sort_order,
        )
        await self.async_refresh_equipment(notify=False)
        await self.async_refresh_exercises(notify=False)
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()

    async def async_update_equipment(
        self,
        equipment_id: str,
        name: str | None = None,
        description: str | None = None,
        icon: str | None = None,
        location: str | None = None,
        enabled: bool | None = None,
        sort_order: int | None = None,
    ) -> bool:
        """Update equipment and refresh runtime caches if changed."""
        updated = await self._store.async_update_equipment(
            equipment_id=equipment_id,
            name=name,
            description=description,
            icon=icon,
            location=location,
            enabled=enabled,
            sort_order=sort_order,
        )
        if updated:
            await self.async_refresh_equipment(notify=False)
            await self.async_refresh_exercises(notify=False)
            await self.async_refresh_statistics(notify=False)
            self._notify_listeners()
        return updated

    async def async_disable_equipment(self, equipment_id: str) -> bool:
        """Disable equipment and refresh runtime caches if changed."""
        updated = await self._store.async_disable_equipment(equipment_id)
        if updated:
            await self.async_refresh_equipment(notify=False)
            await self.async_refresh_exercises(notify=False)
            await self.async_refresh_statistics(notify=False)
            self._notify_listeners()
        return updated

    async def async_assign_exercise_to_equipment(
        self, exercise_id: str, equipment_id: str | None
    ) -> bool:
        """Assign one exercise to equipment and refresh caches."""
        updated = await self._store.async_assign_exercise_to_equipment(exercise_id, equipment_id)
        if updated:
            await self.async_refresh_exercises(notify=False)
            await self.async_refresh_statistics(notify=False)
            self._notify_listeners()
        return updated

    def get_exercise(self, exercise_id: str) -> dict[str, Any] | None:
        """Return one exercise row from the cached catalog."""
        return self._exercise_by_id.get(exercise_id)

    def exercise_options_for_options_flow(
        self, include_disabled: bool = True
    ) -> list[dict[str, str]]:
        """Return SelectSelector options with localized labels for options flow."""
        rows = self._exercises
        if not include_disabled:
            rows = [row for row in rows if int(row.get("enabled", 1)) == 1]

        options: list[dict[str, str]] = []
        for row in rows:
            exercise_id = str(row.get("id") or "")
            if not exercise_id:
                continue
            label = f"{self.exercise_display_name(exercise_id)} ({exercise_id})"
            if int(row.get("enabled", 1)) != 1:
                label += " [disabled]"
            options.append({"value": exercise_id, "label": label})
        return options

    def get_equipment(self, equipment_id: str) -> dict[str, Any] | None:
        """Return one equipment row from cached catalog."""
        return self._equipment_by_id.get(equipment_id)

    def get_equipment_options(self, include_disabled: bool = False) -> list[dict[str, str]]:
        """Return SelectSelector options for equipment."""
        rows = self._equipment
        if not include_disabled:
            rows = [row for row in rows if int(row.get("enabled", 1)) == 1]
        rows = sorted(
            rows,
            key=lambda row: (
                int(row.get("sort_order", 100)),
                str(row.get("name") or row.get("id") or ""),
                str(row.get("id") or ""),
            ),
        )
        options: list[dict[str, str]] = []
        for row in rows:
            equipment_id = str(row.get("id") or "")
            if not equipment_id:
                continue
            label = f"{str(row.get('name') or equipment_id)} ({equipment_id})"
            if int(row.get("enabled", 1)) != 1:
                label += " [disabled]"
            options.append({"value": equipment_id, "label": label})
        return options

    def get_equipment_for_exercise(self, exercise_id: str | None) -> str | None:
        """Return mapped equipment id for one exercise."""
        if not exercise_id:
            return None
        row = self._exercise_by_id.get(exercise_id)
        if row is None:
            return None
        equipment_id = row.get("equipment_id")
        if equipment_id is None:
            return None
        normalized = str(equipment_id).strip()
        return normalized if normalized else None

    def get_exercises_for_equipment(self, equipment_id: str | None) -> list[dict[str, Any]]:
        """Return cached enabled exercises filtered by equipment id."""
        rows = [row for row in self._exercises if int(row.get("enabled", 1)) == 1]
        if equipment_id is None:
            return rows
        return [row for row in rows if str(row.get("equipment_id") or "") == equipment_id]

    def exercise_display_name(self, exercise_id: str | None) -> str:
        """Return localized exercise display name for one id."""
        if not exercise_id:
            return "Unknown"
        row = self._exercise_by_id.get(exercise_id)
        if row is None:
            return exercise_id
        locale = self._locale.lower()
        if locale.startswith("de"):
            return str(row.get("name_de") or row.get("name_en") or exercise_id)
        return str(row.get("name_en") or row.get("name_de") or exercise_id)

    def exercise_id_from_input(self, exercise: str) -> str | None:
        """Resolve exercise id from id or localized label/name."""
        normalized = exercise.strip().lower()
        if not normalized:
            return None
        if normalized in self._exercise_by_id:
            return normalized
        for exercise_id, row in self._exercise_by_id.items():
            candidates = [
                exercise_id,
                str(row.get("name_en") or ""),
                str(row.get("name_de") or ""),
            ]
            if any(normalized == candidate.strip().lower() for candidate in candidates if candidate):
                return exercise_id
        return None

    def _rebuild_exercise_options(self) -> None:
        """Build exercise select options using active equipment filter."""
        self._exercise_display_to_id = {}
        enabled_rows = [row for row in self._exercises if int(row.get("enabled", 1)) == 1]
        if self._active_equipment_id is not None:
            enabled_rows = [
                row
                for row in enabled_rows
                if str(row.get("equipment_id") or "") == self._active_equipment_id
            ]
        enabled_rows.sort(
            key=lambda row: (
                int(row.get("sort_order", 0)),
                str(row.get("name_en") or row.get("id") or ""),
                str(row.get("id") or ""),
            )
        )

        options: list[str] = []
        for row in enabled_rows:
            exercise_id = str(row["id"])
            display = self.exercise_display_name(exercise_id)
            options.append(display)
            self._exercise_display_to_id[display] = exercise_id
        self._exercise_options = options
        self._rebuild_equipment_runtime_state()

        if self._active_exercise_id not in self._exercise_by_id:
            self._active_exercise_id = None
        if self._active_exercise_id is not None and self._active_exercise_id not in [
            str(row["id"]) for row in enabled_rows
        ]:
            self._active_exercise_id = str(enabled_rows[0]["id"]) if enabled_rows else None
        if self._active_exercise_id is None and enabled_rows:
            self._active_exercise_id = str(enabled_rows[0]["id"])

    def _sync_global_runtime_from_active_equipment(self) -> None:
        if self._active_equipment_id is None:
            return
        state = self._ensure_equipment_runtime_state(self._active_equipment_id)
        self._active_exercise_id = state.get("active_exercise_id")
        self._weight = float(state.get("weight", 0.0))
        self._reps = int(state.get("reps", 0))
        self._notes = str(state.get("notes", ""))

    # ------------------------------------------------------------------
    # Startup and statistics
    # ------------------------------------------------------------------

    async def async_initialize(self) -> None:
        """Restore persisted state on integration startup."""
        try:
            await self.resolve_user_id(None)
            await self.async_refresh_users()
            await self.async_refresh_equipment(notify=False)
            await self.async_refresh_exercises(notify=False)

            open_workout = await self._store.async_get_current_open_workout(self._selected_user_id or LEGACY_USER_ID)
            if open_workout is not None:
                self._current_workout_id = int(open_workout["id"])
                self._current_workout_started_at = str(open_workout["started_at"])
                self._current_workout_user_id = str(open_workout.get("user_id") or LEGACY_USER_ID)
                self._workout_state = STATE_ACTIVE
                self._current_set_number = await self._store.async_get_set_count_for_workout(
                    self._current_workout_id
                )
            else:
                self._current_workout_id = None
                self._current_workout_started_at = None
                self._current_workout_user_id = None
                self._workout_state = STATE_READY
                self._current_set_number = 0

            last_set = await self._store.async_get_last_set()
            if last_set is not None:
                self._last_saved_set = last_set
                workout_id = last_set.get("workout_id")
                if workout_id is not None:
                    summary_set_number = await self._store.async_get_set_count_for_workout(
                        int(workout_id)
                    )
                else:
                    summary_set_number = await self._store.async_get_set_count()
                self._last_set_summary = self._format_set_summary(
                    set_number=summary_set_number,
                    exercise=self.exercise_display_name(
                        str(last_set.get("exercise_id")) if last_set.get("exercise_id") else None
                    )
                    if last_set.get("exercise_id")
                    else str(last_set["exercise"]),
                    weight=float(last_set["weight"]),
                    reps=int(last_set["reps"]),
                )
            else:
                self._last_saved_set = None
                self._last_set_summary = None

            await self.async_refresh_statistics(notify=False)
        except sqlite3.Error as err:
            _LOGGER.exception("HA Fitness: failed to initialize coordinator from SQLite")
            raise HomeAssistantError("Failed to initialize HA Fitness storage") from err

        self._notify_listeners()

    async def async_refresh_users(self) -> None:
        """Refresh known users from storage."""
        self._users = await self._store.async_get_users()

        if self._selected_user_id is None:
            if self._current_user_id is not None:
                self._selected_user_id = self._current_user_id
            elif self._users:
                self._selected_user_id = str(self._users[0]["id"])
            else:
                self._selected_user_id = LEGACY_USER_ID

    async def resolve_user_id(self, context_user_id: str | None) -> str:
        """Resolve effective user id from service context and upsert into users table."""
        resolved = context_user_id or self._selected_user_id or self._current_user_id or LEGACY_USER_ID
        fallback_display_name = context_user_id if context_user_id else resolved
        await self._store.async_upsert_user(resolved, fallback_display_name)

        if context_user_id:
            self._current_user_id = resolved
        elif self._current_user_id is None:
            self._current_user_id = resolved

        if self._selected_user_id is None:
            self._selected_user_id = resolved

        return resolved

    async def async_refresh_statistics(self, notify: bool = True) -> None:
        """Refresh cached statistics from SQLite."""
        try:
            await self.async_refresh_users()
            await self.async_refresh_equipment(notify=False)
            personal_user_id = self._selected_user_id or self._current_user_id or LEGACY_USER_ID

            self._total_volume = await self._store.async_get_total_volume()
            self._total_sets = await self._store.async_get_set_count()
            self._total_workouts = await self._store.async_get_workout_count()
            self._recent_sets = await self._store.async_get_recent_sets(10)

            self._personal_total_volume = await self._store.async_get_total_volume(personal_user_id)
            self._personal_total_sets = await self._store.async_get_set_count(personal_user_id)
            self._personal_total_workouts = await self._store.async_get_workout_count(personal_user_id)
            self._personal_recent_sets = await self._store.async_get_recent_sets(10, personal_user_id)

            household_user_ids = self._included_user_ids or None
            self._household_total_volume = await self._store.async_get_household_total_volume(
                household_user_ids
            )
            self._household_total_sets = await self._store.async_get_household_set_count(
                household_user_ids
            )
            self._household_total_workouts = await self._store.async_get_household_workout_count(
                household_user_ids
            )
            self._household_recent_sets = await self._store.async_get_household_recent_sets(
                10, household_user_ids
            )

            for exercise_id in EXERCISE_IDS:
                self._pr_by_exercise[exercise_id] = await self._store.async_get_pr_by_exercise(exercise_id)
                self._volume_by_exercise[
                    exercise_id
                ] = await self._store.async_get_total_volume_by_exercise(exercise_id)

                self._personal_pr_by_exercise[exercise_id] = await self._store.async_get_pr_by_exercise(
                    exercise_id, personal_user_id
                )
                self._personal_volume_by_exercise[
                    exercise_id
                ] = await self._store.async_get_total_volume_by_exercise(
                    exercise_id, personal_user_id
                )

                self._household_pr_by_exercise[
                    exercise_id
                ] = await self._store.async_get_household_pr_by_exercise(
                    exercise_id, household_user_ids
                )
                self._household_volume_by_exercise[
                    exercise_id
                ] = await self._store.async_get_household_total_volume_by_exercise(
                    exercise_id, household_user_ids
                )

            self._exercise_statistics = await self._store.async_get_exercise_statistics(
                personal_user_id, household_user_ids
            )
            equipment_global = await self._store.async_get_equipment_statistics()
            equipment_personal = await self._store.async_get_user_equipment_statistics(personal_user_id)
            equipment_household = await self._store.async_get_household_equipment_statistics(
                household_user_ids
            )
            global_map = {
                str(row.get("equipment_id")): row
                for row in equipment_global
                if row.get("equipment_id")
            }
            personal_map = {
                str(row.get("equipment_id")): row
                for row in equipment_personal
                if row.get("equipment_id")
            }
            household_map = {
                str(row.get("equipment_id")): row
                for row in equipment_household
                if row.get("equipment_id")
            }
            catalog_map = {
                str(row.get("id")): row for row in self._equipment if row.get("id")
            }

            ordered_equipment_ids: list[str] = []
            seen_equipment_ids: set[str] = set()
            for source_rows in (
                equipment_global,
                equipment_personal,
                equipment_household,
                self._equipment,
            ):
                for source_row in source_rows:
                    equipment_id = str(
                        source_row.get("equipment_id") or source_row.get("id") or ""
                    )
                    if not equipment_id or equipment_id in seen_equipment_ids:
                        continue
                    seen_equipment_ids.add(equipment_id)
                    ordered_equipment_ids.append(equipment_id)

            merged_equipment_statistics: list[dict[str, Any]] = []
            for equipment_id in ordered_equipment_ids:
                personal_row = personal_map.get(equipment_id, {})
                household_row = household_map.get(equipment_id, {})
                row = global_map.get(equipment_id)
                if row is None:
                    catalog_row = catalog_map.get(equipment_id, {})
                    enabled_source = (
                        catalog_row.get("enabled")
                        if catalog_row.get("enabled") is not None
                        else personal_row.get("enabled")
                        if personal_row.get("enabled") is not None
                        else household_row.get("enabled")
                    )
                    row = {
                        "equipment_id": equipment_id,
                        "name": (
                            catalog_row.get("name")
                            or personal_row.get("name")
                            or household_row.get("name")
                            or equipment_id
                        ),
                        "icon": (
                            catalog_row.get("icon")
                            or personal_row.get("icon")
                            or household_row.get("icon")
                        ),
                        "location": (
                            catalog_row.get("location")
                            or personal_row.get("location")
                            or household_row.get("location")
                        ),
                        "enabled": _coerce_enabled(enabled_source, default=True),
                        "total_volume": 0.0,
                        "total_sets": 0,
                        "total_trainings": 0,
                        "last_used": None,
                        "top_exercise": None,
                    }

                row["personal_volume"] = float(personal_row.get("total_volume", 0.0))
                row["household_volume"] = float(household_row.get("total_volume", 0.0))
                row["personal_sets"] = int(personal_row.get("total_sets", 0))
                row["household_sets"] = int(household_row.get("total_sets", 0))
                merged_equipment_statistics.append(row)

            self._equipment_statistics = merged_equipment_statistics
            self._equipment_statistics_by_id = {
                str(row.get("equipment_id") or ""): row
                for row in merged_equipment_statistics
                if row.get("equipment_id")
            }
            for row in self._exercise_statistics:
                exercise_id = str(row.get("exercise_id") or "")
                row["display_name"] = (
                    self.exercise_display_name(exercise_id) if exercise_id else "Unknown"
                )
        except sqlite3.Error as err:
            _LOGGER.exception("HA Fitness: failed to refresh statistics")
            raise HomeAssistantError("Failed to refresh statistics") from err

        if notify:
            self._notify_listeners()

    async def async_export_data(self) -> str:
        """Export global, personal, and household statistics to JSON."""
        await self.async_refresh_statistics(notify=False)
        payload = {
            "generated_at": _now_utc().isoformat(),
            "current_user_id": self._current_user_id,
            "selected_user_id": self._selected_user_id,
            "included_user_ids": self._included_user_ids,
            "users": self._users,
            "global": {
                "total_volume": self._total_volume,
                "total_sets": self._total_sets,
                "total_workouts": self._total_workouts,
                "pr_by_exercise": self._pr_by_exercise,
                "volume_by_exercise": self._volume_by_exercise,
                "recent_sets": self._recent_sets,
                "equipment_statistics": self._equipment_statistics,
            },
            "personal": {
                "user_id": self._selected_user_id or self._current_user_id or LEGACY_USER_ID,
                "total_volume": self._personal_total_volume,
                "total_sets": self._personal_total_sets,
                "total_workouts": self._personal_total_workouts,
                "pr_by_exercise": self._personal_pr_by_exercise,
                "volume_by_exercise": self._personal_volume_by_exercise,
                "recent_sets": self._personal_recent_sets,
            },
            "household": {
                "included_user_ids": self._included_user_ids,
                "total_volume": self._household_total_volume,
                "total_sets": self._household_total_sets,
                "total_workouts": self._household_total_workouts,
                "pr_by_exercise": self._household_pr_by_exercise,
                "volume_by_exercise": self._household_volume_by_exercise,
                "recent_sets": self._household_recent_sets,
            },
        }
        export_path = self.hass.config.path("ha_fitness", "export.json")
        try:
            await self.hass.async_add_executor_job(_write_json, export_path, payload)
        except OSError as err:
            _LOGGER.exception("HA Fitness: failed to export data to %s", export_path)
            raise HomeAssistantError("Failed to export data") from err
        _LOGGER.info("HA Fitness: exported data to %s", export_path)
        return export_path

    # ------------------------------------------------------------------
    # Workout lifecycle
    # ------------------------------------------------------------------

    async def start_workout(self, context_user_id: str | None = None) -> None:
        """Transition workout state to active."""
        user_id = await self.resolve_user_id(context_user_id)

        if (
            self._workout_state == STATE_ACTIVE
            and self._current_workout_id is not None
            and self._current_workout_user_id == user_id
        ):
            _LOGGER.debug("HA Fitness: start_workout ignored (already active for %s)", user_id)
            return

        started_at = _now_utc()
        try:
            existing_open = await self._store.async_get_current_open_workout(user_id)
            if existing_open is not None:
                self._current_workout_id = int(existing_open["id"])
                self._current_workout_started_at = str(existing_open["started_at"])
                self._current_workout_user_id = user_id
                self._current_set_number = await self._store.async_get_set_count_for_workout(
                    self._current_workout_id
                )
            else:
                self._current_workout_id = await self._store.async_start_workout(user_id, started_at)
                self._current_workout_started_at = started_at.isoformat()
                self._current_workout_user_id = user_id
                self._current_set_number = 0
        except sqlite3.Error as err:
            _LOGGER.exception("HA Fitness: failed to start workout in SQLite")
            raise HomeAssistantError("Failed to start workout") from err

        self._workout_state = STATE_ACTIVE
        self._last_set_summary = None
        self._last_saved_set = None
        self._notes = ""
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()

    async def finish_workout(self, context_user_id: str | None = None) -> None:
        """Transition workout state to ready for the resolved user."""
        user_id = await self.resolve_user_id(context_user_id)

        try:
            workout_id_to_finish: int | None = None
            if (
                self._workout_state == STATE_ACTIVE
                and self._current_workout_id is not None
                and self._current_workout_user_id == user_id
            ):
                workout_id_to_finish = self._current_workout_id
            else:
                open_workout = await self._store.async_get_current_open_workout(user_id)
                if open_workout is not None:
                    workout_id_to_finish = int(open_workout["id"])

            if workout_id_to_finish is not None:
                await self._store.async_finish_workout(workout_id_to_finish, _now_utc())
        except sqlite3.Error as err:
            _LOGGER.exception("HA Fitness: failed to finish workout in SQLite")
            raise HomeAssistantError("Failed to finish workout") from err

        if self._current_workout_user_id == user_id:
            self._workout_state = STATE_READY
            self._current_workout_id = None
            self._current_workout_started_at = None
            self._current_workout_user_id = None
            self._current_set_number = 0

        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()

    # ------------------------------------------------------------------
    # Set saving
    # ------------------------------------------------------------------

    async def save_current_set(self, context_user_id: str | None = None) -> None:
        """Save a set using the current runtime state with validation."""
        user_id = await self.resolve_user_id(context_user_id)

        if (
            self._current_workout_user_id != user_id
            or self._current_workout_id is None
            or self._workout_state != STATE_ACTIVE
        ):
            open_workout = await self._store.async_get_current_open_workout(user_id)
            if open_workout is not None:
                self._current_workout_id = int(open_workout["id"])
                self._current_workout_started_at = str(open_workout["started_at"])
                self._current_workout_user_id = user_id
                self._workout_state = STATE_ACTIVE
                self._current_set_number = await self._store.async_get_set_count_for_workout(
                    self._current_workout_id
                )

        errors = self._validate_set_inputs(
            exercise_id=self._active_exercise_id,
            weight=self._weight,
            reps=self._reps,
            require_active_workout=True,
            require_current_workout_id=True,
        )
        if errors:
            message = " ".join(errors)
            _LOGGER.warning("HA Fitness save_current_set validation failed: %s", message)
            self.hass.async_create_task(
                self.hass.components.persistent_notification.async_create(
                    message=f"Cannot save set: {message}",
                    title="HA Fitness – Save Set",
                    notification_id="ha_fitness_save_set_error",
                )
            )
            raise HomeAssistantError(message)

        await self._persist_set(
            user_id=user_id,
            workout_id=self._current_workout_id,
            set_number=self._current_set_number + 1,
            exercise_id=self._active_exercise_id,  # type: ignore[arg-type]
            exercise_display=self.exercise_display_name(self._active_exercise_id),
            weight=self._weight,
            reps=self._reps,
            notes=self._notes or None,
        )
        self._current_set_number += 1
        self._notify_listeners()

    async def save_current_set_for_equipment(
        self, equipment_id: str, context_user_id: str | None = None
    ) -> None:
        """Save a set using one equipment runtime state."""
        if equipment_id not in self._equipment_by_id:
            raise HomeAssistantError(f"Unknown equipment_id: {equipment_id}")
        if not self.equipment_enabled(equipment_id):
            raise HomeAssistantError(f"Equipment is disabled: {equipment_id}")

        user_id = await self.resolve_user_id(context_user_id)

        if (
            self._current_workout_user_id != user_id
            or self._current_workout_id is None
            or self._workout_state != STATE_ACTIVE
        ):
            open_workout = await self._store.async_get_current_open_workout(user_id)
            if open_workout is not None:
                self._current_workout_id = int(open_workout["id"])
                self._current_workout_started_at = str(open_workout["started_at"])
                self._current_workout_user_id = user_id
                self._workout_state = STATE_ACTIVE
                self._current_set_number = await self._store.async_get_set_count_for_workout(
                    self._current_workout_id
                )

        state = self._ensure_equipment_runtime_state(equipment_id)
        exercise_id = state.get("active_exercise_id")
        weight = float(state.get("weight", 0.0))
        reps = int(state.get("reps", 0))
        notes = str(state.get("notes", "") or "")

        errors = self._validate_set_inputs(
            exercise_id=str(exercise_id) if exercise_id else None,
            weight=weight,
            reps=reps,
            require_active_workout=True,
            require_current_workout_id=True,
        )
        if errors:
            message = " ".join(errors)
            _LOGGER.warning("HA Fitness save_current_set_for_equipment validation failed: %s", message)
            self.hass.async_create_task(
                self.hass.components.persistent_notification.async_create(
                    message=f"Cannot save set: {message}",
                    title="HA Fitness – Save Set",
                    notification_id="ha_fitness_save_set_error",
                )
            )
            raise HomeAssistantError(message)

        resolved_exercise_id = str(exercise_id)
        await self._persist_set(
            user_id=user_id,
            workout_id=self._current_workout_id,
            set_number=self._current_set_number + 1,
            exercise_id=resolved_exercise_id,
            exercise_display=self.exercise_display_name(resolved_exercise_id),
            weight=weight,
            reps=reps,
            notes=notes or None,
            selected_equipment_id=equipment_id,
        )
        state["last_set_summary"] = self._last_set_summary
        self._current_set_number += 1
        self._notify_listeners()

    async def save_set(
        self,
        exercise: str,
        weight: float,
        reps: int,
        notes: str | None = None,
        context_user_id: str | None = None,
    ) -> None:
        """Save a set with explicitly provided data (used by service call)."""
        user_id = await self.resolve_user_id(context_user_id)
        exercise_id = self.exercise_id_from_input(exercise)
        exercise_display = (
            self.exercise_display_name(exercise_id) if exercise_id is not None else exercise.strip()
        )

        errors = self._validate_set_inputs(
            exercise_id=exercise_id if exercise_id is not None else exercise.strip(),
            weight=weight,
            reps=reps,
            require_active_workout=False,
            require_current_workout_id=False,
        )
        if errors:
            message = " ".join(errors)
            _LOGGER.warning("HA Fitness save_set validation failed: %s", message)
            self.hass.async_create_task(
                self.hass.components.persistent_notification.async_create(
                    message=f"Cannot save set: {message}",
                    title="HA Fitness – Save Set",
                    notification_id="ha_fitness_save_set_error",
                )
            )
            raise HomeAssistantError(message)

        if (
            self._workout_state == STATE_ACTIVE
            and self._current_workout_id is not None
            and self._current_workout_user_id == user_id
        ):
            await self._persist_set(
                user_id=user_id,
                workout_id=self._current_workout_id,
                set_number=self._current_set_number + 1,
                exercise_id=exercise_id,
                exercise_display=exercise_display,
                weight=weight,
                reps=reps,
                notes=notes,
            )
            self._current_set_number += 1
            self._notify_listeners()
            return

        try:
            open_workout = await self._store.async_get_current_open_workout(user_id)
            if open_workout is not None:
                workout_id = int(open_workout["id"])
                set_number = await self._store.async_get_set_count_for_workout(workout_id) + 1
                await self._persist_set(
                    user_id=user_id,
                    workout_id=workout_id,
                    set_number=set_number,
                    exercise_id=exercise_id,
                    exercise_display=exercise_display,
                    weight=weight,
                    reps=reps,
                    notes=notes,
                    refresh_stats=False,
                )
            else:
                workout_id = await self._store.async_start_workout(user_id, _now_utc())
                await self._persist_set(
                    user_id=user_id,
                    workout_id=workout_id,
                    set_number=1,
                    exercise_id=exercise_id,
                    exercise_display=exercise_display,
                    weight=weight,
                    reps=reps,
                    notes=notes,
                    refresh_stats=False,
                )
                await self._store.async_finish_workout(workout_id, _now_utc())

            await self.async_refresh_statistics(notify=False)
        except sqlite3.Error as err:
            _LOGGER.exception("HA Fitness: failed to save set via implicit workout")
            raise HomeAssistantError("Failed to save set") from err

        self._notify_listeners()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_set_inputs(
        self,
        exercise_id: str | None,
        weight: float,
        reps: int,
        *,
        require_active_workout: bool,
        require_current_workout_id: bool,
    ) -> list[str]:
        """Validate set input values and return a list of error messages."""
        errors: list[str] = []
        if require_active_workout and self._workout_state != STATE_ACTIVE:
            errors.append("No active workout. Press Start Workout first.")
        if require_current_workout_id and self._current_workout_id is None:
            errors.append("No active workout id. Press Start Workout again.")
        if not exercise_id:
            errors.append("No exercise selected.")
        if weight <= 0:
            errors.append("Weight must be greater than 0.")
        if reps <= 0:
            errors.append("Reps must be greater than 0.")
        return errors

    async def _persist_set(
        self,
        user_id: str,
        workout_id: int | None,
        set_number: int,
        exercise_id: str | None,
        exercise_display: str,
        weight: float,
        reps: int,
        notes: str | None,
        refresh_stats: bool = True,
        selected_equipment_id: str | None = None,
    ) -> None:
        volume = weight * reps
        created_at = _now_utc()
        resolved_equipment_id = (
            selected_equipment_id
            if selected_equipment_id is not None
            else self._active_equipment_id or self.get_equipment_for_exercise(exercise_id)
        )
        try:
            set_id = await self._store.async_save_set(
                user_id=user_id,
                workout_id=workout_id,
                exercise=exercise_display,
                exercise_id=exercise_id,
                equipment_id=resolved_equipment_id,
                weight=weight,
                reps=reps,
                volume=volume,
                notes=notes,
                created_at=created_at,
            )
        except sqlite3.Error as err:
            _LOGGER.exception("HA Fitness: failed to write set to SQLite")
            raise HomeAssistantError("Failed to save set") from err

        self._last_set_summary = self._format_set_summary(
            set_number=set_number,
            exercise=exercise_display,
            weight=weight,
            reps=reps,
        )
        self._last_saved_set = {
            "id": set_id,
            "user_id": user_id,
            "workout_id": workout_id,
            "set_number": set_number,
            "exercise": exercise_display,
            "exercise_id": exercise_id,
            "equipment_id": resolved_equipment_id,
            "weight": weight,
            "reps": reps,
            "volume": volume,
            "notes": notes,
            "created_at": created_at.isoformat(),
        }
        _LOGGER.info("HA Fitness: %s (user=%s, notes=%s)", self._last_set_summary, user_id, notes)

        if refresh_stats:
            await self.async_refresh_statistics(notify=False)

    def _ensure_equipment_runtime_state(self, equipment_id: str) -> dict[str, Any]:
        state = self._equipment_runtime_state.get(equipment_id)
        if state is None:
            state = {
                "active_exercise_id": None,
                "weight": 0.0,
                "reps": 0,
                "notes": "",
                "last_set_summary": None,
            }
            self._equipment_runtime_state[equipment_id] = state
        return state

    def _rebuild_equipment_runtime_state(self) -> None:
        previous = self._equipment_runtime_state
        rebuilt: dict[str, dict[str, Any]] = {}
        for equipment_id in self.enabled_equipment_ids:
            prior = previous.get(equipment_id, {})
            exercises = self.get_exercises_for_equipment(equipment_id)
            valid_exercise_ids = [str(row.get("id") or "") for row in exercises if row.get("id")]
            active_exercise_id = (
                str(prior.get("active_exercise_id")) if prior.get("active_exercise_id") else None
            )
            if active_exercise_id not in valid_exercise_ids:
                active_exercise_id = valid_exercise_ids[0] if valid_exercise_ids else None
            rebuilt[equipment_id] = {
                "active_exercise_id": active_exercise_id,
                "weight": float(prior.get("weight", 0.0)),
                "reps": int(prior.get("reps", 0)),
                "notes": str(prior.get("notes", "")),
                "last_set_summary": prior.get("last_set_summary"),
            }
        self._equipment_runtime_state = rebuilt
        if self._active_equipment_id is not None:
            self._sync_global_runtime_from_active_equipment()

    def _format_set_summary(
        self,
        *,
        set_number: int,
        exercise: str,
        weight: float,
        reps: int,
    ) -> str:
        return f"Set {set_number}: {exercise} - {weight} kg x {reps}"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _write_json(path: str, payload: dict[str, Any]) -> None:
    """Create parent directory if needed and write payload as formatted JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _coerce_enabled(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default
