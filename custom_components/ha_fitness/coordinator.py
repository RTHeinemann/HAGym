"""HAGym coordinator."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
import os
import sqlite3
from collections.abc import Callable
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later

from .const import (
    DEFAULT_METRIC_TYPE,
    EXERCISE_IDS,
    IDLE_EQUIPMENT_ID,
    IDLE_EXERCISE_ID,
    LEGACY_USER_ID,
    METRIC_TYPE_BODYWEIGHT,
    METRIC_TYPE_CARDIO,
    METRIC_TYPE_CUSTOM,
    METRIC_TYPE_DISTANCE,
    METRIC_TYPE_DURATION,
    METRIC_TYPE_HOLD,
    METRIC_TYPE_STRENGTH,
    STATE_ACTIVE,
    STATE_READY,
    SUPPORTED_METRIC_TYPES,
)
from .storage import HAFitnessStore

_LOGGER = logging.getLogger(__name__)
_ANALYTICS_TOP_LIMIT = 20
_WEEKLY_HISTORY_DEFAULT_WEEKS = 12
_WEEKLY_HISTORY_MAX_WEEKS = 26
_PUSH_MUSCLE_GROUP_IDS = {"chest", "shoulders", "triceps"}
_PULL_MUSCLE_GROUP_IDS = {
    "back",
    "lats",
    "rhomboids",
    "traps",
    "biceps",
    "forearms",
    "erector_spinae",
}
_LEGS_MUSCLE_GROUP_IDS = {
    "quadriceps",
    "hamstrings",
    "glutes",
    "calves",
    "adductors",
    "abductors",
}
_CORE_MUSCLE_GROUP_IDS = {"core", "abs", "obliques"}
_CONFIRM_ACTION_START = "start_workout"
_CONFIRM_ACTION_FINISH = "finish_workout"
_STATE_START_CONFIRM = "start_confirm"
_STATE_FINISH_CONFIRM = "finish_confirm"
_INTENSITY_LOW = "low"
_INTENSITY_MODERATE = "moderate"
_INTENSITY_HARD = "hard"
_INTENSITY_VERY_HARD = "very_hard"
_SUPPORTED_INTENSITY_VALUES = {
    _INTENSITY_LOW,
    _INTENSITY_MODERATE,
    _INTENSITY_HARD,
    _INTENSITY_VERY_HARD,
}


class HAFitnessCoordinator:
    """Manages runtime state for the HAGym integration."""

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
        self._duration_minutes: float = 0.0
        self._distance_km: float = 0.0
        self._calories: float = 0.0
        self._steps: int = 0
        self._avg_heart_rate: float = 0.0
        self._max_heart_rate: float = 0.0
        self._added_weight: float = 0.0
        self._intensity: str = _INTENSITY_MODERATE
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
        self._active_equipment_is_idle: bool = True
        self._equipment: list[dict[str, Any]] = []
        self._equipment_by_id: dict[str, dict[str, Any]] = {}
        self._equipment_display_to_id: dict[str, str] = {}
        self._equipment_options: list[str] = []
        self._equipment_statistics: list[dict[str, Any]] = []
        self._equipment_statistics_by_id: dict[str, dict[str, Any]] = {}
        self._equipment_runtime_state: dict[str, dict[str, Any]] = {}
        self._muscle_groups: list[dict[str, Any]] = []
        self._muscle_group_by_id: dict[str, dict[str, Any]] = {}
        self._exercise_muscle_group_map_by_exercise: dict[str, list[dict[str, Any]]] = {}
        self._muscle_group_statistics: list[dict[str, Any]] = []
        self._muscle_group_statistics_by_id: dict[str, dict[str, Any]] = {}
        self._personal_weekly_summary: dict[str, Any] = {}
        self._personal_weekly_exercise_statistics: dict[str, Any] = {}
        self._personal_weekly_muscle_group_statistics: dict[str, Any] = {}
        self._personal_weekly_volume_history: dict[str, Any] = {}
        self._personal_training_balance: dict[str, Any] = {}
        self._household_weekly_summary: dict[str, Any] = {}
        self._recent_workouts: list[dict[str, Any]] = []
        self._recent_workouts_user_id: str | None = None
        self._recent_workouts_limit: int = 20
        self._selected_workout: dict[str, Any] | None = None
        self._selected_workout_sets: list[dict[str, Any]] = []
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
        self._exercise_metric_stats_global: dict[str, dict[str, Any]] = {}
        self._exercise_metric_stats_personal: dict[str, dict[str, Any]] = {}
        self._exercise_metric_stats_household: dict[str, dict[str, Any]] = {}
        self._listeners: list[Callable[[], None]] = []
        self._pending_confirmation_action: str | None = None
        self._pending_confirmation_expires_at: datetime | None = None
        self._confirmation_timeout_seconds: int = 10
        self._pending_confirmation_unsub: Callable[[], None] | None = None

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
        self._expire_confirmation_if_needed(notify=False)
        if self._pending_confirmation_action == _CONFIRM_ACTION_START:
            return _STATE_START_CONFIRM
        if self._pending_confirmation_action == _CONFIRM_ACTION_FINISH:
            return _STATE_FINISH_CONFIRM
        return self._workout_state

    @property
    def is_workout_active(self) -> bool:
        return self._workout_state == STATE_ACTIVE

    @property
    def pending_confirmation_action(self) -> str | None:
        self._expire_confirmation_if_needed(notify=False)
        return self._pending_confirmation_action

    @property
    def pending_confirmation_expires_at(self) -> str | None:
        self._expire_confirmation_if_needed(notify=False)
        if self._pending_confirmation_expires_at is None:
            return None
        return self._pending_confirmation_expires_at.isoformat()

    @property
    def confirmation_seconds_remaining(self) -> int:
        return self._confirmation_seconds_remaining()

    @property
    def active_exercise(self) -> str | None:
        return self._active_exercise_id

    @property
    def active_exercise_display(self) -> str | None:
        if not self.is_workout_active or self._active_exercise_id is None:
            return self._idle_exercise_label
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
    def duration_minutes(self) -> float:
        return self._duration_minutes

    @property
    def distance_km(self) -> float:
        return self._distance_km

    @property
    def calories(self) -> float:
        return self._calories

    @property
    def steps(self) -> int:
        return self._steps

    @property
    def avg_heart_rate(self) -> float:
        return self._avg_heart_rate

    @property
    def max_heart_rate(self) -> float:
        return self._max_heart_rate

    @property
    def added_weight(self) -> float:
        return self._added_weight

    @property
    def intensity(self) -> str:
        return self._intensity

    @property
    def active_exercise_metric_type(self) -> str:
        return self.exercise_metric_type(self._active_exercise_id)

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
        if not self.is_workout_active or self._active_equipment_is_idle:
            return self._idle_equipment_label
        if self._active_equipment_id is None:
            return self._all_equipment_label
        row = self._equipment_by_id.get(self._active_equipment_id)
        if row is None:
            return self._idle_equipment_label
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
    def muscle_groups(self) -> list[dict[str, Any]]:
        return self._muscle_groups

    @property
    def muscle_group_statistics(self) -> list[dict[str, Any]]:
        return self._muscle_group_statistics

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
                self._equipment_name_from_row(row) or str(row.get("id") or ""),
                str(row.get("id") or ""),
            )
        )
        return [str(row["id"]) for row in rows]

    @property
    def enabled_exercise_ids(self) -> list[str]:
        rows = [
            row
            for row in self._exercises
            if row.get("id") is not None and int(row.get("enabled", 1)) == 1
        ]
        rows.sort(
            key=lambda row: (
                int(row.get("sort_order", 0)),
                str(row.get("name_en") or row.get("id") or ""),
                str(row.get("id") or ""),
            )
        )
        return [str(row["id"]) for row in rows]

    @property
    def enabled_muscle_group_ids(self) -> list[str]:
        rows = [
            row
            for row in self._muscle_groups
            if row.get("id") is not None and int(row.get("enabled", 1)) == 1
        ]
        rows.sort(
            key=lambda row: (
                int(row.get("sort_order", 100)),
                str(row.get("name_en") or row.get("id") or ""),
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

    def get_exercise_metric_statistics(
        self, exercise_id: str, scope: str = "personal"
    ) -> dict[str, Any]:
        """Return cached metric-type-aware statistics for one exercise and scope."""
        if scope == "global":
            return self._exercise_metric_stats_global.get(exercise_id, {})
        if scope == "household":
            return self._exercise_metric_stats_household.get(exercise_id, {})
        return self._exercise_metric_stats_personal.get(exercise_id, {})

    def get_personal_weekly_summary(self) -> dict[str, Any]:
        return self._personal_weekly_summary

    def get_personal_weekly_exercise_statistics(self) -> dict[str, Any]:
        return self._personal_weekly_exercise_statistics

    def get_personal_weekly_muscle_group_statistics(self) -> dict[str, Any]:
        return self._personal_weekly_muscle_group_statistics

    def get_personal_weekly_volume_history(self) -> dict[str, Any]:
        return self._personal_weekly_volume_history

    def get_personal_training_balance(self) -> dict[str, Any]:
        return self._personal_training_balance

    def get_household_weekly_summary(self) -> dict[str, Any]:
        return self._household_weekly_summary

    def get_recent_workouts(self) -> list[dict[str, Any]]:
        return self._recent_workouts

    def get_recent_workouts_user_id(self) -> str | None:
        return self._recent_workouts_user_id

    def get_recent_workouts_limit(self) -> int:
        return self._recent_workouts_limit

    def get_selected_workout(self) -> dict[str, Any] | None:
        return self._selected_workout

    def get_selected_workout_sets(self) -> list[dict[str, Any]]:
        return self._selected_workout_sets

    def _exercise_name_from_row(self, row: dict[str, Any] | None) -> str | None:
        if row is None:
            return None
        exercise_id = str(row.get("exercise_id") or "").strip()
        if exercise_id:
            return self.exercise_display_name(exercise_id)
        if self._locale.lower().startswith("de"):
            return str(row.get("name_de") or row.get("name_en") or "") or None
        return str(row.get("name_en") or row.get("name_de") or "") or None

    def _muscle_group_name_from_row(self, row: dict[str, Any] | None) -> str | None:
        if row is None:
            return None
        muscle_group_id = str(row.get("muscle_group_id") or "").strip()
        if muscle_group_id:
            return self.muscle_group_display_name(muscle_group_id)
        if self._locale.lower().startswith("de"):
            return str(row.get("name_de") or row.get("name_en") or "") or None
        return str(row.get("name_en") or row.get("name_de") or "") or None

    def _equipment_name_from_row(self, row: dict[str, Any] | None) -> str | None:
        if row is None:
            return None
        return (
            str(
                row.get("name_de")
                or row.get("name_en")
                or row.get("name")
                or row.get("equipment_id")
                or row.get("id")
                or ""
            )
            or None
        )

    def exercise_enabled(self, exercise_id: str) -> bool:
        row = self._exercise_by_id.get(exercise_id)
        if row is None:
            return False
        return int(row.get("enabled", 1)) == 1

    def get_exercise_muscle_group_mapping(
        self, exercise_id: str
    ) -> list[dict[str, Any]]:
        return list(self._exercise_muscle_group_map_by_exercise.get(exercise_id, []))

    def get_exercise_muscle_group_attributes(
        self, exercise_id: str
    ) -> dict[str, Any]:
        rows = self.get_exercise_muscle_group_mapping(exercise_id)
        primary: list[str] = []
        secondary: list[str] = []
        stabilizer: list[str] = []
        mapping: list[dict[str, Any]] = []

        for row in rows:
            muscle_group_id = str(row.get("muscle_group_id") or "")
            if not muscle_group_id:
                continue
            role = str(row.get("role") or "primary")
            weight_factor = float(row.get("weight_factor") or 0.0)
            muscle_group_name = self.muscle_group_display_name(muscle_group_id)

            mapping.append(
                {
                    "muscle_group_id": muscle_group_id,
                    "muscle_group_name": muscle_group_name,
                    "role": role,
                    "weight_factor": weight_factor,
                }
            )
            if role == "primary":
                primary.append(muscle_group_name)
            elif role == "secondary":
                secondary.append(muscle_group_name)
            else:
                stabilizer.append(muscle_group_name)

        return {
            "primary_muscle_groups": primary,
            "secondary_muscle_groups": secondary,
            "stabilizer_muscle_groups": stabilizer,
            "muscle_group_mapping": mapping,
        }

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

    @property
    def _idle_equipment_label(self) -> str:
        return "Equipment wählen" if self._locale.lower().startswith("de") else "Select equipment"

    @property
    def _idle_exercise_label(self) -> str:
        return "Übung wählen" if self._locale.lower().startswith("de") else "Select exercise"

    @property
    def _all_equipment_label(self) -> str:
        return "Alle Geräte" if self._locale.lower().startswith("de") else "All Equipment"

    def _localized_text(self, de_text: str, en_text: str) -> str:
        return de_text if self._locale.lower().startswith("de") else en_text

    def _reset_live_input_state(self) -> None:
        """Reset live workout input selectors and fields to idle state."""
        self._active_equipment_id = None
        self._active_equipment_is_idle = True
        self._active_exercise_id = None
        self._weight = 0.0
        self._reps = 0
        self._notes = ""
        self._duration_minutes = 0.0
        self._distance_km = 0.0
        self._calories = 0.0
        self._steps = 0
        self._avg_heart_rate = 0.0
        self._max_heart_rate = 0.0
        self._added_weight = 0.0
        self._intensity = _INTENSITY_MODERATE
        for equipment_id in self.enabled_equipment_ids:
            state = self._ensure_equipment_runtime_state(equipment_id)
            state["active_exercise_id"] = None
            state["weight"] = 0.0
            state["reps"] = 0
            state["notes"] = ""
        self._rebuild_exercise_options()

    def _set_pending_confirmation(self, action: str) -> None:
        """Set pending two-step confirmation action and schedule expiration."""
        if action not in {_CONFIRM_ACTION_START, _CONFIRM_ACTION_FINISH}:
            raise ValueError(f"Invalid confirmation action: {action}")

        self._clear_pending_confirmation(notify=False)
        self._pending_confirmation_action = action
        self._pending_confirmation_expires_at = _now_utc() + timedelta(
            seconds=self._confirmation_timeout_seconds
        )
        self._pending_confirmation_unsub = async_call_later(
            self.hass,
            self._confirmation_timeout_seconds,
            self._handle_confirmation_timeout,
        )

    def _clear_pending_confirmation(self, notify: bool = False) -> bool:
        """Clear pending confirmation state and cancel timeout callback."""
        changed = (
            self._pending_confirmation_action is not None
            or self._pending_confirmation_expires_at is not None
            or self._pending_confirmation_unsub is not None
        )
        if self._pending_confirmation_unsub is not None:
            self._pending_confirmation_unsub()
            self._pending_confirmation_unsub = None
        self._pending_confirmation_action = None
        self._pending_confirmation_expires_at = None
        if changed and notify:
            self._notify_listeners()
        return changed

    def _expire_confirmation_if_needed(self, notify: bool = False) -> bool:
        """Expire pending confirmation when timeout has elapsed."""
        if (
            self._pending_confirmation_action is None
            or self._pending_confirmation_expires_at is None
        ):
            return False
        if _now_utc() < self._pending_confirmation_expires_at:
            return False
        expired_action = self._pending_confirmation_action
        self._clear_pending_confirmation(notify=notify)
        _LOGGER.debug("HAGym: confirmation expired for action %s", expired_action)
        return True

    def _is_pending_confirmation(self, action: str) -> bool:
        """Return True if action is the currently active pending confirmation."""
        self._expire_confirmation_if_needed(notify=False)
        return self._pending_confirmation_action == action

    def _confirmation_seconds_remaining(self) -> int:
        """Return seconds remaining for the current pending confirmation."""
        self._expire_confirmation_if_needed(notify=False)
        if self._pending_confirmation_expires_at is None:
            return 0
        remaining = (self._pending_confirmation_expires_at - _now_utc()).total_seconds()
        return max(0, int(remaining))

    @callback
    def _handle_confirmation_timeout(self, _now: datetime) -> None:
        """Scheduled callback to expire pending confirmation."""
        self._pending_confirmation_unsub = None
        if self._expire_confirmation_if_needed(notify=False):
            _LOGGER.debug("HAGym: confirmation expired")
            self._notify_listeners()

    async def async_shutdown(self) -> None:
        """Release coordinator resources on config-entry unload."""
        self._clear_pending_confirmation(notify=False)

    # ------------------------------------------------------------------
    # Setters (called by entities)
    # ------------------------------------------------------------------

    def set_active_exercise(self, exercise_id: str) -> None:
        """Update the currently selected exercise by stable id."""
        if not self.is_workout_active:
            self._active_exercise_id = None
            self._notify_listeners()
            return
        if exercise_id == IDLE_EXERCISE_ID:
            self._active_exercise_id = None
            self._notify_listeners()
            return
        if exercise_id not in self._exercise_by_id:
            _LOGGER.warning("HAGym: unknown exercise_id '%s' ignored", exercise_id)
            return
        self._active_exercise_id = exercise_id
        if self._active_equipment_id is not None:
            state = self._ensure_equipment_runtime_state(self._active_equipment_id)
            state["active_exercise_id"] = exercise_id
        _LOGGER.debug("HAGym: active exercise set to %s", exercise_id)
        self._notify_listeners()

    def set_active_exercise_option(self, option: str) -> None:
        """Set active exercise using localized select option label."""
        if option == self._idle_exercise_label:
            self._active_exercise_id = None
            self._notify_listeners()
            return
        if not self.is_workout_active:
            self._active_exercise_id = None
            self._notify_listeners()
            return
        exercise_id = self._exercise_display_to_id.get(option)
        if exercise_id is None:
            _LOGGER.warning("HAGym: unknown exercise option '%s' ignored", option)
            return
        self._active_exercise_id = exercise_id
        if self._active_equipment_id is not None:
            state = self._ensure_equipment_runtime_state(self._active_equipment_id)
            state["active_exercise_id"] = exercise_id
        _LOGGER.debug("HAGym: active exercise option set to %s -> %s", option, exercise_id)
        self._notify_listeners()

    def set_active_equipment(
        self, equipment_id: str | None, context_user_id: str | None = None
    ) -> None:
        """Update currently selected equipment id (None means no filter)."""
        if context_user_id:
            self._current_user_id = context_user_id
            if self._selected_user_id is None:
                self._selected_user_id = context_user_id
        if equipment_id is not None:
            row = self._equipment_by_id.get(equipment_id)
            if row is None:
                _LOGGER.warning("HAGym: unknown equipment_id '%s' ignored", equipment_id)
                return
            if int(row.get("enabled", 1)) != 1:
                _LOGGER.warning("HAGym: disabled equipment_id '%s' ignored", equipment_id)
                return
        if not self.is_workout_active:
            self._active_equipment_id = None
            self._active_equipment_is_idle = True
            self._active_exercise_id = None
            self._rebuild_exercise_options()
            self._notify_listeners()
            return
        self._active_equipment_id = equipment_id
        self._active_equipment_is_idle = False
        if equipment_id is None:
            self._active_exercise_id = None
        self._rebuild_exercise_options()
        self._sync_global_runtime_from_active_equipment()
        self._notify_listeners()

    def set_active_equipment_option(self, option: str) -> None:
        """Set active equipment from select option label."""
        if option == self._idle_equipment_label:
            self._active_equipment_id = None
            self._active_equipment_is_idle = True
            self._active_exercise_id = None
            self._rebuild_exercise_options()
            self._notify_listeners()
            return
        if option == self._all_equipment_label:
            self.set_active_equipment(None)
            return
        equipment_id = self._equipment_display_to_id.get(option)
        if equipment_id is None:
            _LOGGER.warning("HAGym: unknown equipment option '%s' ignored", option)
            return
        self.set_active_equipment(equipment_id)

    def set_weight(self, weight: float) -> None:
        """Update the current weight value."""
        self._weight = weight
        if self._active_equipment_id is not None:
            state = self._ensure_equipment_runtime_state(self._active_equipment_id)
            state["weight"] = float(weight)
        _LOGGER.debug("HAGym: weight set to %s", weight)
        self._notify_listeners()

    def set_reps(self, reps: int) -> None:
        """Update the current reps value."""
        self._reps = reps
        if self._active_equipment_id is not None:
            state = self._ensure_equipment_runtime_state(self._active_equipment_id)
            state["reps"] = int(reps)
        _LOGGER.debug("HAGym: reps set to %s", reps)
        self._notify_listeners()

    def set_notes(self, notes: str) -> None:
        """Update the current notes value."""
        self._notes = notes
        if self._active_equipment_id is not None:
            state = self._ensure_equipment_runtime_state(self._active_equipment_id)
            state["notes"] = notes
        _LOGGER.debug("HAGym: notes updated")
        self._notify_listeners()

    def set_duration_minutes(self, value: float) -> None:
        """Update the current activity duration in minutes."""
        self._duration_minutes = max(0.0, float(value))
        self._notify_listeners()

    def set_distance_km(self, value: float) -> None:
        """Update the current activity distance in kilometers."""
        self._distance_km = max(0.0, float(value))
        self._notify_listeners()

    def set_calories(self, value: float) -> None:
        """Update current calories input."""
        self._calories = max(0.0, float(value))
        self._notify_listeners()

    def set_steps(self, value: int) -> None:
        """Update current steps input."""
        self._steps = max(0, int(value))
        self._notify_listeners()

    def set_avg_heart_rate(self, value: float) -> None:
        """Update average heart rate input."""
        self._avg_heart_rate = max(0.0, float(value))
        self._notify_listeners()

    def set_max_heart_rate(self, value: float) -> None:
        """Update max heart rate input."""
        self._max_heart_rate = max(0.0, float(value))
        self._notify_listeners()

    def set_added_weight(self, value: float) -> None:
        """Update added weight input for bodyweight activities."""
        self._added_weight = max(0.0, float(value))
        self._notify_listeners()

    def set_intensity(self, value: str) -> None:
        """Update selected intensity value for cardio activities."""
        normalized = str(value or "").strip().lower()
        if normalized not in _SUPPORTED_INTENSITY_VALUES:
            _LOGGER.warning("HAGym: invalid intensity '%s' ignored", value)
            return
        self._intensity = normalized
        self._notify_listeners()

    def get_activity_required_fields(self) -> list[str]:
        """Return required fields for the selected exercise metric type."""
        metric_type = self.active_exercise_metric_type
        if metric_type in (METRIC_TYPE_DURATION, METRIC_TYPE_HOLD, METRIC_TYPE_CARDIO):
            return ["duration_minutes"]
        if metric_type == METRIC_TYPE_DISTANCE:
            return ["distance_km"]
        if metric_type == METRIC_TYPE_BODYWEIGHT:
            return ["reps"]
        if metric_type == METRIC_TYPE_CUSTOM:
            return [
                "duration_minutes|distance_km|calories|steps|reps|added_weight",
            ]
        return []

    def activity_input_enabled(self) -> bool:
        """Return whether activity inputs are currently actionable."""
        if not self.is_workout_active:
            return False
        if not self._active_exercise_id or self._active_exercise_id == IDLE_EXERCISE_ID:
            return False
        return self.exercise_metric_type(self._active_exercise_id) != METRIC_TYPE_STRENGTH

    def equipment_display_name(self, equipment_id: str) -> str:
        """Return configured equipment display name or fallback to equipment_id."""
        row = self._equipment_by_id.get(equipment_id)
        if row is None:
            return equipment_id
        return self._equipment_name_from_row(row) or equipment_id

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
                "HAGym: invalid equipment exercise assignment '%s' for equipment '%s'",
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
            "HAGym: unknown equipment exercise option '%s' for equipment '%s'",
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

    def muscle_group_display_name(self, muscle_group_id: str) -> str:
        """Return localized muscle group display name for one id."""
        row = self._muscle_group_by_id.get(muscle_group_id)
        if row is None:
            return muscle_group_id
        locale = self._locale.lower()
        if locale.startswith("de"):
            return str(row.get("name_de") or row.get("name_en") or muscle_group_id)
        return str(row.get("name_en") or row.get("name_de") or muscle_group_id)

    def get_muscle_group(self, muscle_group_id: str) -> dict[str, Any] | None:
        """Return one muscle group row from cached catalog."""
        return self._muscle_group_by_id.get(muscle_group_id)

    def get_muscle_group_statistics(self, muscle_group_id: str) -> dict[str, Any]:
        """Return one muscle group statistics row from cache."""
        return self._muscle_group_statistics_by_id.get(muscle_group_id, {})

    def muscle_group_options_for_options_flow(
        self, include_disabled: bool = True
    ) -> list[dict[str, str]]:
        """Return SelectSelector options for muscle groups in options flow."""
        rows = self._muscle_groups
        if not include_disabled:
            rows = [row for row in rows if int(row.get("enabled", 1)) == 1]
        rows = sorted(
            rows,
            key=lambda row: (
                int(row.get("sort_order", 100)),
                str(row.get("name_en") or row.get("id") or ""),
                str(row.get("id") or ""),
            ),
        )
        options: list[dict[str, str]] = []
        for row in rows:
            muscle_group_id = str(row.get("id") or "")
            if not muscle_group_id:
                continue
            label = f"{self.muscle_group_display_name(muscle_group_id)} ({muscle_group_id})"
            if int(row.get("enabled", 1)) != 1:
                label += " [disabled]"
            options.append({"value": muscle_group_id, "label": label})
        return options

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
            _LOGGER.exception("HAGym: failed to refresh exercises")
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
            _LOGGER.exception("HAGym: failed to refresh equipment")
            raise HomeAssistantError("Failed to refresh equipment") from err

        self._equipment = rows
        self._equipment_by_id = {
            str(row["id"]): row for row in rows if row.get("id") is not None
        }
        enabled_rows = [row for row in rows if int(row.get("enabled", 1)) == 1]
        enabled_rows.sort(
            key=lambda row: (
                int(row.get("sort_order", 100)),
                self._equipment_name_from_row(row) or str(row.get("id") or ""),
                str(row.get("id") or ""),
            )
        )
        self._equipment_display_to_id = {}
        options = [self._idle_equipment_label, self._all_equipment_label]
        for row in enabled_rows:
            equipment_id = str(row["id"])
            display = self._equipment_name_from_row(row) or equipment_id
            options.append(display)
            self._equipment_display_to_id[display] = equipment_id
        self._equipment_options = options
        self._rebuild_equipment_runtime_state()

        if self._active_equipment_id not in self._equipment_by_id:
            self._active_equipment_id = None
            self._active_equipment_is_idle = True
        self._rebuild_exercise_options()

        if notify:
            self._notify_listeners()

    async def async_refresh_muscle_groups(self, notify: bool = True) -> None:
        """Refresh muscle group catalog from storage."""
        try:
            rows = await self._store.async_get_muscle_groups(enabled_only=False)
            self._muscle_groups = rows
            self._muscle_group_by_id = {
                str(row["id"]): row for row in rows if row.get("id") is not None
            }
            mapping_by_exercise: dict[str, list[dict[str, Any]]] = {}
            for exercise_id in self.enabled_exercise_ids:
                mapping_by_exercise[exercise_id] = (
                    await self._store.async_get_muscle_groups_for_exercise(exercise_id)
                )
            self._exercise_muscle_group_map_by_exercise = mapping_by_exercise
        except sqlite3.Error as err:
            _LOGGER.exception("HAGym: failed to refresh muscle groups")
            raise HomeAssistantError("Failed to refresh muscle groups") from err
        if notify:
            self._notify_listeners()

    async def async_refresh_muscle_statistics(
        self,
        notify: bool = True,
        *,
        personal_user_id: str | None = None,
        household_user_ids: list[str] | None = None,
    ) -> None:
        """Refresh muscle-group statistics for global/personal/household scopes."""
        effective_personal_user_id = personal_user_id or self._resolve_personal_user_id()
        _LOGGER.debug(
            "HAGym personal statistics user_id resolved to %s",
            effective_personal_user_id,
        )
        try:
            rows = await self._store.async_get_muscle_group_statistics(
                effective_personal_user_id, household_user_ids
            )
        except sqlite3.Error as err:
            _LOGGER.exception("HAGym: failed to refresh muscle group statistics")
            raise HomeAssistantError("Failed to refresh muscle group statistics") from err

        self._muscle_group_statistics = rows
        self._muscle_group_statistics_by_id = {
            str(row.get("muscle_group_id") or ""): row
            for row in rows
            if row.get("muscle_group_id")
        }
        if notify:
            self._notify_listeners()

    async def async_refresh_weekly_analytics(
        self,
        notify: bool = True,
        *,
        personal_user_id: str | None = None,
        household_user_ids: list[str] | None = None,
    ) -> None:
        """Refresh current-week aggregate analytics caches."""
        effective_personal_user_id = personal_user_id or self._resolve_personal_user_id()
        effective_household_user_ids = household_user_ids or self._included_user_ids
        timezone_name, week_start_local, week_end_local, week_start_utc, week_end_utc = (
            _current_week_bounds(self.hass)
        )

        personal_summary_base = await self._store.async_get_weekly_summary(
            week_start_utc,
            week_end_utc,
            user_id=effective_personal_user_id,
        )
        personal_exercises_rows = await self._store.async_get_weekly_exercise_statistics(
            week_start_utc,
            week_end_utc,
            user_id=effective_personal_user_id,
        )
        personal_muscle_rows = await self._store.async_get_weekly_muscle_group_statistics(
            week_start_utc,
            week_end_utc,
            user_id=effective_personal_user_id,
        )

        personal_exercises = _limit_rows(personal_exercises_rows, _ANALYTICS_TOP_LIMIT)
        personal_muscles = _limit_rows(personal_muscle_rows, _ANALYTICS_TOP_LIMIT)
        top_personal_exercise = personal_exercises[0] if personal_exercises else None
        top_personal_muscle = personal_muscles[0] if personal_muscles else None

        self._personal_weekly_summary = {
            "user_id": effective_personal_user_id,
            "week_start": week_start_local,
            "week_end": week_end_local,
            "timezone": timezone_name,
            "total_volume": float(personal_summary_base.get("total_volume", 0.0)),
            "total_sets": int(personal_summary_base.get("total_sets", 0)),
            "workout_count": int(personal_summary_base.get("workout_count", 0)),
            "active_days": int(personal_summary_base.get("active_days", 0)),
            "average_volume_per_workout": _safe_div(
                float(personal_summary_base.get("total_volume", 0.0)),
                int(personal_summary_base.get("workout_count", 0)),
            ),
            "average_sets_per_workout": _safe_div(
                int(personal_summary_base.get("total_sets", 0)),
                int(personal_summary_base.get("workout_count", 0)),
            ),
            "top_exercise_id": (
                str(top_personal_exercise.get("exercise_id"))
                if top_personal_exercise is not None and top_personal_exercise.get("exercise_id")
                else None
            ),
            "top_exercise_name": (
                self._exercise_name_from_row(top_personal_exercise)
                if top_personal_exercise is not None
                else None
            ),
            "top_exercise_volume": float(
                top_personal_exercise.get("volume", 0.0)
                if top_personal_exercise is not None
                else 0.0
            ),
            "top_muscle_group_id": (
                str(top_personal_muscle.get("muscle_group_id"))
                if top_personal_muscle is not None and top_personal_muscle.get("muscle_group_id")
                else None
            ),
            "top_muscle_group_name": (
                self._muscle_group_name_from_row(top_personal_muscle)
                if top_personal_muscle is not None
                else None
            ),
            "top_muscle_group_volume": float(
                top_personal_muscle.get("volume", 0.0)
                if top_personal_muscle is not None
                else 0.0
            ),
            "last_set_at": personal_summary_base.get("last_set_at"),
            "last_workout_at": personal_summary_base.get("last_workout_at"),
        }

        personal_exercises_payload = [
            {
                "exercise_id": row.get("exercise_id"),
                "exercise_name": self._exercise_name_from_row(row),
                "volume": float(row.get("volume", 0.0)),
                "sets": int(row.get("sets", 0)),
                "max_weight": float(row.get("max_weight", 0.0)),
                "avg_weight": float(row.get("avg_weight", 0.0)),
                "avg_reps": float(row.get("avg_reps", 0.0)),
                "last_used_at": row.get("last_used_at"),
                "equipment_ids": list(row.get("equipment_ids") or []),
                "equipment_names": list(row.get("equipment_names") or []),
            }
            for row in personal_exercises
        ]
        self._personal_weekly_exercise_statistics = {
            "user_id": effective_personal_user_id,
            "week_start": week_start_local,
            "week_end": week_end_local,
            "timezone": timezone_name,
            "exercise_count": len(personal_exercises_rows),
            "exercises": personal_exercises_payload,
        }

        personal_muscles_payload = [
            {
                "muscle_group_id": row.get("muscle_group_id"),
                "muscle_group_name": self._muscle_group_name_from_row(row),
                "body_region": row.get("body_region"),
                "volume": float(row.get("volume", 0.0)),
                "sets": int(row.get("sets", 0)),
                "top_exercise_id": row.get("top_exercise_id"),
                "top_exercise_name": self._exercise_name_from_row(
                    {
                        "name_en": row.get("top_exercise_name_en"),
                        "name_de": row.get("top_exercise_name_de"),
                        "exercise_id": row.get("top_exercise_id"),
                    }
                ),
                "last_used_at": row.get("last_used_at"),
            }
            for row in personal_muscles
        ]
        personal_muscle_total_volume = sum(
            float(row.get("volume", 0.0)) for row in personal_muscle_rows
        )
        self._personal_weekly_muscle_group_statistics = {
            "user_id": effective_personal_user_id,
            "week_start": week_start_local,
            "week_end": week_end_local,
            "timezone": timezone_name,
            "total_volume": float(personal_muscle_total_volume),
            "muscle_group_count": len(personal_muscle_rows),
            "muscle_groups": personal_muscles_payload,
        }

        self._personal_training_balance = _build_training_balance(
            locale=self._locale,
            user_id=effective_personal_user_id,
            week_start=week_start_local,
            week_end=week_end_local,
            muscle_groups=personal_muscles_payload,
        )
        await self.async_refresh_weekly_volume_history(
            notify=False,
            personal_user_id=effective_personal_user_id,
        )

        household_summary_base = await self._store.async_get_weekly_summary(
            week_start_utc,
            week_end_utc,
            user_ids=effective_household_user_ids,
        )
        household_exercises_rows = await self._store.async_get_weekly_exercise_statistics(
            week_start_utc,
            week_end_utc,
            user_ids=effective_household_user_ids,
        )
        household_muscle_rows = await self._store.async_get_weekly_muscle_group_statistics(
            week_start_utc,
            week_end_utc,
            user_ids=effective_household_user_ids,
        )
        household_user_rows = await self._store.async_get_weekly_user_statistics(
            week_start_utc,
            week_end_utc,
            user_ids=effective_household_user_ids,
        )
        household_exercises = _limit_rows(household_exercises_rows, _ANALYTICS_TOP_LIMIT)
        household_muscles = _limit_rows(household_muscle_rows, _ANALYTICS_TOP_LIMIT)
        household_users = _limit_rows(household_user_rows, _ANALYTICS_TOP_LIMIT)
        top_household_exercise = household_exercises[0] if household_exercises else None
        top_household_muscle = household_muscles[0] if household_muscles else None
        top_household_user = household_users[0] if household_users else None

        resolved_included_user_ids = (
            list(effective_household_user_ids)
            if effective_household_user_ids is not None
            else [
                str(row.get("id"))
                for row in self._users
                if row.get("id") and _coerce_enabled(row.get("enabled"), default=True)
            ]
        )

        self._household_weekly_summary = {
            "included_user_ids": (
                resolved_included_user_ids if resolved_included_user_ids else None
            ),
            "week_start": week_start_local,
            "week_end": week_end_local,
            "timezone": timezone_name,
            "total_volume": float(household_summary_base.get("total_volume", 0.0)),
            "total_sets": int(household_summary_base.get("total_sets", 0)),
            "workout_count": int(household_summary_base.get("workout_count", 0)),
            "active_users": len(household_user_rows),
            "active_days": int(household_summary_base.get("active_days", 0)),
            "top_user_id": (
                str(top_household_user.get("user_id"))
                if top_household_user is not None and top_household_user.get("user_id")
                else None
            ),
            "top_user_name": (
                str(
                    top_household_user.get("display_name")
                    or top_household_user.get("user_id")
                )
                if top_household_user is not None
                else None
            ),
            "top_user_volume": float(
                top_household_user.get("volume", 0.0)
                if top_household_user is not None
                else 0.0
            ),
            "top_exercise_id": (
                str(top_household_exercise.get("exercise_id"))
                if top_household_exercise is not None
                and top_household_exercise.get("exercise_id")
                else None
            ),
            "top_exercise_name": (
                self._exercise_name_from_row(top_household_exercise)
                if top_household_exercise is not None
                else None
            ),
            "top_exercise_volume": float(
                top_household_exercise.get("volume", 0.0)
                if top_household_exercise is not None
                else 0.0
            ),
            "top_muscle_group_id": (
                str(top_household_muscle.get("muscle_group_id"))
                if top_household_muscle is not None
                and top_household_muscle.get("muscle_group_id")
                else None
            ),
            "top_muscle_group_name": (
                self._muscle_group_name_from_row(top_household_muscle)
                if top_household_muscle is not None
                else None
            ),
            "top_muscle_group_volume": float(
                top_household_muscle.get("volume", 0.0)
                if top_household_muscle is not None
                else 0.0
            ),
            "users": [
                {
                    "user_id": row.get("user_id"),
                    "display_name": row.get("display_name") or row.get("user_id"),
                    "volume": float(row.get("volume", 0.0)),
                    "sets": int(row.get("sets", 0)),
                    "workout_count": int(row.get("workout_count", 0)),
                    "last_set_at": row.get("last_set_at"),
                }
                for row in household_users
            ],
            "last_set_at": household_summary_base.get("last_set_at"),
            "last_workout_at": household_summary_base.get("last_workout_at"),
        }

        if notify:
            self._notify_listeners()

    async def async_refresh_weekly_volume_history(
        self,
        notify: bool = True,
        *,
        personal_user_id: str | None = None,
    ) -> None:
        """Refresh personal weekly volume history cache."""
        effective_personal_user_id = personal_user_id or self._resolve_personal_user_id()
        timezone_name, week_ranges = _weekly_ranges(
            self.hass,
            weeks=_WEEKLY_HISTORY_DEFAULT_WEEKS,
            max_weeks=_WEEKLY_HISTORY_MAX_WEEKS,
        )
        history_rows = await self._store.async_get_weekly_volume_history(
            week_ranges,
            user_id=effective_personal_user_id,
        )
        weeks_payload: list[dict[str, Any]] = []
        for row in history_rows:
            localized_top_exercise_name = self._exercise_name_from_row(
                {
                    "exercise_id": row.get("top_exercise_id"),
                    "name_en": row.get("top_exercise_name_en"),
                    "name_de": row.get("top_exercise_name_de"),
                }
            )
            localized_top_muscle_name = self._muscle_group_name_from_row(
                {
                    "muscle_group_id": row.get("top_muscle_group_id"),
                    "name_en": row.get("top_muscle_group_name_en"),
                    "name_de": row.get("top_muscle_group_name_de"),
                }
            )
            weeks_payload.append(
                {
                    "week_start": row.get("week_start"),
                    "week_end": row.get("week_end"),
                    "week_label": row.get("week_label"),
                    "iso_year": int(row.get("iso_year", 0)),
                    "iso_week": int(row.get("iso_week", 0)),
                    "total_volume": float(row.get("total_volume", 0.0)),
                    "categorized_volume_total": float(
                        row.get("categorized_volume_total", 0.0)
                    ),
                    "push_volume": float(row.get("push_volume", 0.0)),
                    "pull_volume": float(row.get("pull_volume", 0.0)),
                    "legs_volume": float(row.get("legs_volume", 0.0)),
                    "core_volume": float(row.get("core_volume", 0.0)),
                    "upper_body_volume": float(row.get("upper_body_volume", 0.0)),
                    "lower_body_volume": float(row.get("lower_body_volume", 0.0)),
                    "push_percent": float(row.get("push_percent", 0.0)),
                    "pull_percent": float(row.get("pull_percent", 0.0)),
                    "legs_percent": float(row.get("legs_percent", 0.0)),
                    "core_percent": float(row.get("core_percent", 0.0)),
                    "upper_body_percent": float(row.get("upper_body_percent", 0.0)),
                    "lower_body_percent": float(row.get("lower_body_percent", 0.0)),
                    "total_sets": int(row.get("total_sets", 0)),
                    "workout_count": int(row.get("workout_count", 0)),
                    "active_days": int(row.get("active_days", 0)),
                    "top_exercise_id": row.get("top_exercise_id"),
                    "top_exercise_name": localized_top_exercise_name,
                    "top_exercise_volume": float(row.get("top_exercise_volume", 0.0)),
                    "top_muscle_group_id": row.get("top_muscle_group_id"),
                    "top_muscle_group_name": localized_top_muscle_name,
                    "top_muscle_group_volume": float(
                        row.get("top_muscle_group_volume", 0.0)
                    ),
                }
            )
        current_week = weeks_payload[-1] if weeks_payload else {}
        self._personal_weekly_volume_history = {
            "user_id": effective_personal_user_id,
            "timezone": timezone_name,
            "week_count": len(weeks_payload),
            "current_week_start": current_week.get("week_start"),
            "current_week_end": current_week.get("week_end"),
            "weeks": weeks_payload,
        }
        if notify:
            self._notify_listeners()

    async def async_refresh_workout_history(
        self,
        notify: bool = True,
        *,
        user_id: str | None = None,
        limit: int = 20,
        sets_limit: int = 50,
    ) -> None:
        """Refresh personal workout history cache for management/dashboard use."""
        effective_user_id = user_id or self._resolve_personal_user_id()
        workout_rows = await self._store.async_get_workouts(
            user_id=effective_user_id, limit=limit, offset=0
        )
        workouts_payload: list[dict[str, Any]] = []
        for workout_row in workout_rows:
            workout_id = int(workout_row.get("id", 0))
            if workout_id <= 0:
                continue
            set_rows = await self._store.async_get_sets_for_workout(workout_id)
            set_rows = list(set_rows[: max(1, int(sets_limit))])
            exercise_volume: dict[str, float] = {}
            muscle_volume: dict[str, float] = {}
            sets_payload: list[dict[str, Any]] = []
            for set_row in set_rows:
                exercise_id = str(set_row.get("exercise_id") or "")
                equipment_id = str(set_row.get("equipment_id") or "")
                volume = float(set_row.get("volume", 0.0))
                if exercise_id:
                    exercise_volume[exercise_id] = exercise_volume.get(exercise_id, 0.0) + volume
                    for mapping in self.get_exercise_muscle_group_mapping(exercise_id):
                        muscle_group_id = str(mapping.get("muscle_group_id") or "")
                        if not muscle_group_id:
                            continue
                        weight_factor = float(mapping.get("weight_factor") or 1.0)
                        muscle_volume[muscle_group_id] = (
                            muscle_volume.get(muscle_group_id, 0.0) + (volume * weight_factor)
                        )
                exercise_name = (
                    self.exercise_display_name(exercise_id)
                    if exercise_id
                    else str(set_row.get("exercise") or "")
                )
                equipment_name = (
                    str(
                        set_row.get("equipment_name_de")
                        or set_row.get("equipment_name_en")
                        or set_row.get("equipment_name")
                        or ""
                    )
                    or (
                        self.equipment_display_name(equipment_id)
                        if equipment_id and self.get_equipment(equipment_id)
                        else ""
                    )
                    or equipment_id
                    or None
                )
                sets_payload.append(
                    {
                        "set_id": int(set_row.get("id", 0)),
                        "equipment_id": equipment_id or None,
                        "equipment_name": equipment_name,
                        "exercise_id": exercise_id or None,
                        "exercise_name": exercise_name,
                        "metric_type": str(set_row.get("metric_type") or DEFAULT_METRIC_TYPE),
                        "weight": float(set_row.get("weight", 0.0)),
                        "reps": int(set_row.get("reps", 0)),
                        "volume": volume,
                        "duration_seconds": (
                            int(set_row["duration_seconds"])
                            if set_row.get("duration_seconds") is not None
                            else None
                        ),
                        "distance_m": (
                            float(set_row["distance_m"])
                            if set_row.get("distance_m") is not None
                            else None
                        ),
                        "calories": (
                            float(set_row["calories"])
                            if set_row.get("calories") is not None
                            else None
                        ),
                        "steps": (
                            int(set_row["steps"]) if set_row.get("steps") is not None else None
                        ),
                        "avg_heart_rate": (
                            float(set_row["avg_heart_rate"])
                            if set_row.get("avg_heart_rate") is not None
                            else None
                        ),
                        "max_heart_rate": (
                            float(set_row["max_heart_rate"])
                            if set_row.get("max_heart_rate") is not None
                            else None
                        ),
                        "avg_power_watts": (
                            float(set_row["avg_power_watts"])
                            if set_row.get("avg_power_watts") is not None
                            else None
                        ),
                        "max_power_watts": (
                            float(set_row["max_power_watts"])
                            if set_row.get("max_power_watts") is not None
                            else None
                        ),
                        "avg_speed_mps": (
                            float(set_row["avg_speed_mps"])
                            if set_row.get("avg_speed_mps") is not None
                            else None
                        ),
                        "load_score": (
                            float(set_row["load_score"])
                            if set_row.get("load_score") is not None
                            else None
                        ),
                        "intensity": set_row.get("intensity"),
                        "source": set_row.get("source"),
                        "added_weight": (
                            float(set_row["added_weight"])
                            if set_row.get("added_weight") is not None
                            else None
                        ),
                        "notes": set_row.get("notes"),
                        "created_at": set_row.get("created_at"),
                    }
                )

            top_exercise_id = max(exercise_volume, key=exercise_volume.get) if exercise_volume else None
            top_muscle_group_id = max(muscle_volume, key=muscle_volume.get) if muscle_volume else None
            started_at = workout_row.get("started_at")
            ended_at = workout_row.get("ended_at")
            workouts_payload.append(
                {
                    "workout_id": workout_id,
                    "user_id": workout_row.get("user_id"),
                    "started_at": started_at,
                    "ended_at": ended_at,
                    "duration_minutes": _duration_minutes(started_at, ended_at),
                    "status": workout_row.get("status"),
                    "notes": workout_row.get("notes"),
                    "total_volume": float(workout_row.get("total_volume", 0.0)),
                    "total_sets": int(workout_row.get("total_sets", 0)),
                    "exercise_count": int(workout_row.get("exercise_count", 0)),
                    "equipment_count": int(workout_row.get("equipment_count", 0)),
                    "top_exercise_id": top_exercise_id,
                    "top_exercise_name": (
                        self.exercise_display_name(top_exercise_id)
                        if top_exercise_id
                        else None
                    ),
                    "top_exercise_volume": float(
                        exercise_volume.get(top_exercise_id, 0.0) if top_exercise_id else 0.0
                    ),
                    "top_muscle_group_id": top_muscle_group_id,
                    "top_muscle_group_name": (
                        self.muscle_group_display_name(top_muscle_group_id)
                        if top_muscle_group_id
                        else None
                    ),
                    "top_muscle_group_volume": float(
                        muscle_volume.get(top_muscle_group_id, 0.0)
                        if top_muscle_group_id
                        else 0.0
                    ),
                    "sets": sets_payload,
                }
            )

        self._recent_workouts = workouts_payload
        self._recent_workouts_user_id = effective_user_id
        self._recent_workouts_limit = max(1, int(limit))
        self._selected_workout = workouts_payload[0] if workouts_payload else None
        self._selected_workout_sets = (
            list(self._selected_workout.get("sets", []))
            if self._selected_workout is not None
            else []
        )
        if notify:
            self._notify_listeners()

    async def async_create_manual_workout(
        self,
        *,
        started_at: datetime,
        ended_at: datetime | None = None,
        notes: str | None = None,
        status: str | None = None,
        user_id: str | None = None,
        context_user_id: str | None = None,
    ) -> dict[str, Any]:
        if ended_at is not None and started_at > ended_at:
            raise HomeAssistantError("started_at must be before or equal to ended_at.")
        resolved_user_id = (
            await self.resolve_user_id(user_id)
            if user_id is not None
            else await self.resolve_user_id(context_user_id)
        )
        workout = await self._store.async_create_workout(
            user_id=resolved_user_id,
            started_at=started_at,
            ended_at=ended_at,
            notes=notes,
            status=status or ("active" if ended_at is None else "completed"),
        )
        await self.async_refresh_workout_history(notify=False, user_id=resolved_user_id)
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()
        return workout

    async def async_update_existing_workout(
        self,
        workout_id: int,
        *,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        notes: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        if started_at is not None and ended_at is not None and started_at > ended_at:
            raise HomeAssistantError("started_at must be before or equal to ended_at.")
        workout = await self._store.async_update_workout(
            workout_id=workout_id,
            started_at=started_at,
            ended_at=ended_at,
            notes=notes,
            status=status,
        )
        await self.async_refresh_workout_history(notify=False)
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()
        return workout

    async def async_delete_existing_workout(
        self, workout_id: int, *, delete_sets: bool = True
    ) -> None:
        await self._store.async_delete_workout(workout_id, delete_sets=delete_sets)
        await self.async_refresh_workout_history(notify=False)
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()

    async def async_add_set_to_existing_workout(
        self,
        *,
        workout_id: int,
        exercise_id: str,
        weight: float,
        reps: int,
        equipment_id: str | None = None,
        notes: str | None = None,
        created_at: datetime | None = None,
        user_id: str | None = None,
        context_user_id: str | None = None,
    ) -> dict[str, Any]:
        if weight < 0:
            raise HomeAssistantError("weight must be >= 0.")
        if reps < 1:
            raise HomeAssistantError("reps must be >= 1.")
        exercise_row = self.get_exercise(exercise_id)
        if exercise_row is None:
            raise HomeAssistantError(f"Unknown exercise_id: {exercise_id}")
        if int(exercise_row.get("enabled", 1)) != 1:
            raise HomeAssistantError(f"Exercise is disabled: {exercise_id}")
        if self.exercise_metric_type(exercise_id) != METRIC_TYPE_STRENGTH:
            raise HomeAssistantError(
                "add_set_to_workout currently supports strength exercises only. Use save_activity for non-strength activities."
            )
        if equipment_id:
            equipment_row = self.get_equipment(equipment_id)
            if equipment_row is None:
                raise HomeAssistantError(f"Unknown equipment_id: {equipment_id}")
        resolved_user_id = (
            await self.resolve_user_id(user_id)
            if user_id is not None
            else await self.resolve_user_id(context_user_id)
        )
        set_row = await self._store.async_add_set_to_workout(
            workout_id=workout_id,
            user_id=resolved_user_id,
            equipment_id=equipment_id,
            exercise_id=exercise_id,
            weight=weight,
            reps=reps,
            notes=notes,
            created_at=created_at,
        )
        await self.async_refresh_workout_history(notify=False, user_id=resolved_user_id)
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()
        return set_row

    async def async_update_existing_set(
        self,
        set_id: int,
        *,
        equipment_id: str | None = None,
        exercise_id: str | None = None,
        weight: float | None = None,
        reps: int | None = None,
        notes: str | None = None,
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        if weight is not None and weight < 0:
            raise HomeAssistantError("weight must be >= 0.")
        if reps is not None and reps < 1:
            raise HomeAssistantError("reps must be >= 1.")
        if exercise_id is not None:
            exercise_row = self.get_exercise(exercise_id)
            if exercise_row is None:
                raise HomeAssistantError(f"Unknown exercise_id: {exercise_id}")
            if int(exercise_row.get("enabled", 1)) != 1:
                raise HomeAssistantError(f"Exercise is disabled: {exercise_id}")
        if equipment_id is not None and equipment_id != "":
            equipment_row = self.get_equipment(equipment_id)
            if equipment_row is None:
                raise HomeAssistantError(f"Unknown equipment_id: {equipment_id}")
        set_row = await self._store.async_update_set(
            set_id=set_id,
            equipment_id=equipment_id,
            exercise_id=exercise_id,
            weight=weight,
            reps=reps,
            notes=notes,
            created_at=created_at,
        )
        await self.async_refresh_workout_history(notify=False)
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()
        return set_row

    async def async_delete_existing_set(self, set_id: int) -> None:
        await self._store.async_delete_set(set_id)
        await self.async_refresh_workout_history(notify=False)
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()

    async def async_add_exercise(
        self,
        exercise_id: str,
        name_en: str,
        name_de: str | None = None,
        muscle_group: str | None = None,
        equipment: str | None = None,
        equipment_id: str | None = None,
        metric_type: str | None = None,
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
            metric_type=metric_type,
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
        metric_type: str | None = None,
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
            metric_type=metric_type,
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

    async def async_add_muscle_group(
        self,
        muscle_group_id: str,
        name_en: str,
        name_de: str | None = None,
        description: str | None = None,
        icon: str | None = None,
        body_region: str | None = None,
        enabled: bool = True,
        sort_order: int = 100,
    ) -> None:
        """Add one muscle group and refresh runtime caches."""
        await self._store.async_add_muscle_group(
            muscle_group_id=muscle_group_id,
            name_en=name_en,
            name_de=name_de,
            description=description,
            icon=icon,
            body_region=body_region,
            enabled=enabled,
            sort_order=sort_order,
        )
        await self.async_refresh_muscle_groups(notify=False)
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()

    async def async_update_muscle_group(
        self,
        muscle_group_id: str,
        name_en: str | None = None,
        name_de: str | None = None,
        description: str | None = None,
        icon: str | None = None,
        body_region: str | None = None,
        enabled: bool | None = None,
        sort_order: int | None = None,
    ) -> bool:
        """Update one muscle group and refresh runtime caches if changed."""
        updated = await self._store.async_update_muscle_group(
            muscle_group_id=muscle_group_id,
            name_en=name_en,
            name_de=name_de,
            description=description,
            icon=icon,
            body_region=body_region,
            enabled=enabled,
            sort_order=sort_order,
        )
        if updated:
            await self.async_refresh_muscle_groups(notify=False)
            await self.async_refresh_statistics(notify=False)
            self._notify_listeners()
        return updated

    async def async_disable_muscle_group(self, muscle_group_id: str) -> bool:
        """Disable one muscle group and refresh runtime caches if changed."""
        updated = await self._store.async_disable_muscle_group(muscle_group_id)
        if updated:
            await self.async_refresh_muscle_groups(notify=False)
            await self.async_refresh_statistics(notify=False)
            self._notify_listeners()
        return updated

    async def async_assign_muscle_group_to_exercise(
        self,
        exercise_id: str,
        muscle_group_id: str,
        role: str,
        weight_factor: float,
    ) -> None:
        """Assign one muscle group to one exercise and refresh caches."""
        await self._store.async_assign_muscle_group_to_exercise(
            exercise_id=exercise_id,
            muscle_group_id=muscle_group_id,
            role=role,
            weight_factor=weight_factor,
        )
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()

    async def async_remove_muscle_group_from_exercise(
        self, exercise_id: str, muscle_group_id: str
    ) -> bool:
        """Remove one muscle-group mapping from one exercise."""
        removed = await self._store.async_remove_muscle_group_from_exercise(
            exercise_id=exercise_id,
            muscle_group_id=muscle_group_id,
        )
        if removed:
            await self.async_refresh_statistics(notify=False)
            self._notify_listeners()
        return removed

    async def async_replace_muscle_groups_for_exercise(
        self,
        exercise_id: str,
        primary_ids: list[str],
        secondary_ids: list[str],
        stabilizer_ids: list[str],
    ) -> None:
        """Replace all muscle-group mappings for one exercise."""
        await self._store.async_replace_muscle_groups_for_exercise(
            exercise_id=exercise_id,
            primary_ids=primary_ids,
            secondary_ids=secondary_ids,
            stabilizer_ids=stabilizer_ids,
        )
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()

    async def async_add_equipment(
        self,
        equipment_id: str,
        name: str | None = None,
        name_en: str | None = None,
        name_de: str | None = None,
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
            name_en=name_en,
            name_de=name_de,
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
        name_en: str | None = None,
        name_de: str | None = None,
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
            name_en=name_en,
            name_de=name_de,
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
                self._equipment_name_from_row(row) or str(row.get("id") or ""),
                str(row.get("id") or ""),
            ),
        )
        options: list[dict[str, str]] = []
        for row in rows:
            equipment_id = str(row.get("id") or "")
            if not equipment_id:
                continue
            label = f"{self._equipment_name_from_row(row) or equipment_id} ({equipment_id})"
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

    async def async_get_muscle_groups_for_exercise(
        self, exercise_id: str
    ) -> list[dict[str, Any]]:
        """Return mapped muscle groups for one exercise from storage."""
        return await self._store.async_get_muscle_groups_for_exercise(exercise_id)

    async def async_get_exercises_for_muscle_group(
        self, muscle_group_id: str
    ) -> list[dict[str, Any]]:
        """Return mapped exercises for one muscle group from storage."""
        return await self._store.async_get_exercises_for_muscle_group(muscle_group_id)

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

    def exercise_metric_type(self, exercise_id: str | None) -> str:
        """Return one exercise metric type with safe default fallback."""
        if not exercise_id:
            return DEFAULT_METRIC_TYPE
        row = self._exercise_by_id.get(exercise_id)
        if row is None:
            return DEFAULT_METRIC_TYPE
        raw = str(row.get("metric_type") or DEFAULT_METRIC_TYPE).strip().lower()
        if raw in SUPPORTED_METRIC_TYPES:
            return raw
        return DEFAULT_METRIC_TYPE

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

        options: list[str] = [self._idle_exercise_label]
        if not self.is_workout_active:
            self._exercise_options = options
            self._active_exercise_id = None
            self._rebuild_equipment_runtime_state()
            return
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
            self._active_exercise_id = None

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
            await self.async_refresh_users()
            await self.async_refresh_equipment(notify=False)
            await self.async_refresh_exercises(notify=False)
            await self.async_refresh_muscle_groups(notify=False)

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

            open_workout = await self._store.async_get_current_open_workout(
                self._resolve_personal_user_id()
            )
            if open_workout is not None:
                self._current_workout_id = int(open_workout["id"])
                self._current_workout_started_at = str(open_workout["started_at"])
                self._current_workout_user_id = str(open_workout.get("user_id") or LEGACY_USER_ID)
                if self._current_user_id is None:
                    self._current_user_id = self._current_workout_user_id
                if self._selected_user_id is None:
                    self._selected_user_id = self._current_workout_user_id
                self._workout_state = STATE_ACTIVE
                self._current_set_number = await self._store.async_get_set_count_for_workout(
                    self._current_workout_id
                )
                self._reset_live_input_state()
            else:
                self._current_workout_id = None
                self._current_workout_started_at = None
                self._current_workout_user_id = None
                self._workout_state = STATE_READY
                self._current_set_number = 0
                self._reset_live_input_state()
            self._clear_pending_confirmation(notify=False)

            await self.async_refresh_statistics(notify=False)
        except sqlite3.Error as err:
            _LOGGER.exception("HAGym: failed to initialize coordinator from SQLite")
            raise HomeAssistantError("Failed to initialize HAGym storage") from err

        self._notify_listeners()

    async def async_refresh_users(self) -> None:
        """Refresh known users from storage."""
        self._users = await self._store.async_get_users()

        if self._selected_user_id is None and self._current_user_id is not None:
            self._selected_user_id = self._current_user_id

    async def resolve_user_id(self, context_user_id: str | None) -> str:
        """Resolve effective user id from service context and upsert into users table."""
        resolved = context_user_id or self._resolve_personal_user_id()
        fallback_display_name = context_user_id if context_user_id else resolved
        await self._store.async_upsert_user(resolved, fallback_display_name)

        if context_user_id:
            self._current_user_id = resolved
        elif self._current_user_id is None:
            self._current_user_id = resolved

        if self._selected_user_id is None:
            self._selected_user_id = resolved

        return resolved

    def _resolve_personal_user_id(self) -> str:
        """Return the user id used for personal statistics."""
        if self._selected_user_id:
            return self._selected_user_id
        if self._current_user_id:
            return self._current_user_id
        if self._current_workout_user_id:
            return self._current_workout_user_id
        if self._last_saved_set:
            last_saved_user_id = self._last_saved_set.get("user_id")
            if isinstance(last_saved_user_id, str) and last_saved_user_id:
                return last_saved_user_id
        return LEGACY_USER_ID

    async def async_refresh_statistics(self, notify: bool = True) -> None:
        """Refresh cached statistics from SQLite."""
        try:
            await self.async_refresh_users()
            await self.async_refresh_equipment(notify=False)
            await self.async_refresh_muscle_groups(notify=False)
            personal_user_id = self._resolve_personal_user_id()
            _LOGGER.debug(
                "HAGym personal statistics user_id resolved to %s",
                personal_user_id,
            )

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

            statistics_exercise_ids = list(
                dict.fromkeys(
                    [
                        *EXERCISE_IDS,
                        *[
                            str(row["id"])
                            for row in self._exercises
                            if row.get("id") is not None
                        ],
                    ]
                )
            )
            for exercise_id in statistics_exercise_ids:
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
            await self.async_refresh_exercise_metric_statistics(
                notify=False,
                personal_user_id=personal_user_id,
                household_user_ids=household_user_ids,
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
                            self._equipment_name_from_row(catalog_row)
                            or self._equipment_name_from_row(personal_row)
                            or self._equipment_name_from_row(household_row)
                            or catalog_row.get("name")
                            or personal_row.get("name")
                            or household_row.get("name")
                            or equipment_id
                        ),
                        "name_en": (
                            catalog_row.get("name_en")
                            or personal_row.get("name_en")
                            or household_row.get("name_en")
                        ),
                        "name_de": (
                            catalog_row.get("name_de")
                            or personal_row.get("name_de")
                            or household_row.get("name_de")
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
                else:
                    row["name"] = self._equipment_name_from_row(row) or str(
                        row.get("name") or equipment_id
                    )

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

            await self.async_refresh_muscle_statistics(
                notify=False,
                personal_user_id=personal_user_id,
                household_user_ids=household_user_ids,
            )
            await self.async_refresh_weekly_analytics(
                notify=False,
                personal_user_id=personal_user_id,
                household_user_ids=household_user_ids,
            )
            await self.async_refresh_workout_history(
                notify=False,
                user_id=personal_user_id,
            )
        except sqlite3.Error as err:
            _LOGGER.exception("HAGym: failed to refresh statistics")
            raise HomeAssistantError("Failed to refresh statistics") from err

        if notify:
            self._notify_listeners()

    async def async_refresh_exercise_metric_statistics(
        self,
        notify: bool = True,
        personal_user_id: str | None = None,
        household_user_ids: list[str] | None = None,
    ) -> None:
        """Refresh metric-type-aware exercise statistics caches."""
        resolved_personal_user_id = personal_user_id or self._resolve_personal_user_id()
        resolved_household_user_ids = (
            household_user_ids if household_user_ids is not None else self._included_user_ids
        )
        if resolved_household_user_ids is None:
            resolved_household_user_ids = [
                str(row.get("id"))
                for row in self._users
                if row.get("id") is not None and int(row.get("enabled", 1)) == 1
            ]
            if not resolved_household_user_ids:
                resolved_household_user_ids = [LEGACY_USER_ID]

        global_stats: dict[str, dict[str, Any]] = {}
        personal_stats: dict[str, dict[str, Any]] = {}
        household_stats: dict[str, dict[str, Any]] = {}
        seen_ids: set[str] = set()
        exercise_ids: list[str] = []

        for source_id in [*EXERCISE_IDS, *self.enabled_exercise_ids]:
            if source_id in seen_ids:
                continue
            seen_ids.add(source_id)
            exercise_ids.append(source_id)

        for exercise_id in exercise_ids:
            metric_type = self.exercise_metric_type(exercise_id)
            global_stats[exercise_id] = await self._store.async_get_exercise_metric_statistics(
                exercise_id=exercise_id,
                metric_type=metric_type,
            )
            personal_stats[exercise_id] = await self._store.async_get_exercise_metric_statistics(
                exercise_id=exercise_id,
                metric_type=metric_type,
                user_id=resolved_personal_user_id,
            )
            household_stats[
                exercise_id
            ] = await self._store.async_get_exercise_metric_statistics(
                exercise_id=exercise_id,
                metric_type=metric_type,
                user_ids=resolved_household_user_ids,
            )

        self._exercise_metric_stats_global = global_stats
        self._exercise_metric_stats_personal = personal_stats
        self._exercise_metric_stats_household = household_stats

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
                "muscle_group_statistics": self._muscle_group_statistics,
                "exercise_metric_statistics": self._exercise_metric_stats_global,
            },
            "personal": {
                "user_id": self._resolve_personal_user_id(),
                "total_volume": self._personal_total_volume,
                "total_sets": self._personal_total_sets,
                "total_workouts": self._personal_total_workouts,
                "pr_by_exercise": self._personal_pr_by_exercise,
                "volume_by_exercise": self._personal_volume_by_exercise,
                "recent_sets": self._personal_recent_sets,
                "recent_workouts": self._recent_workouts,
                "weekly_summary": self._personal_weekly_summary,
                "weekly_exercise_statistics": self._personal_weekly_exercise_statistics,
                "weekly_muscle_group_statistics": self._personal_weekly_muscle_group_statistics,
                "weekly_volume_history": self._personal_weekly_volume_history,
                "training_balance": self._personal_training_balance,
                "exercise_metric_statistics": self._exercise_metric_stats_personal,
            },
            "household": {
                "included_user_ids": self._included_user_ids,
                "total_volume": self._household_total_volume,
                "total_sets": self._household_total_sets,
                "total_workouts": self._household_total_workouts,
                "pr_by_exercise": self._household_pr_by_exercise,
                "volume_by_exercise": self._household_volume_by_exercise,
                "recent_sets": self._household_recent_sets,
                "weekly_summary": self._household_weekly_summary,
                "exercise_metric_statistics": self._exercise_metric_stats_household,
            },
        }
        export_path = self.hass.config.path("ha_fitness", "export.json")
        try:
            await self.hass.async_add_executor_job(_write_json, export_path, payload)
        except OSError as err:
            _LOGGER.exception("HAGym: failed to export data to %s", export_path)
            raise HomeAssistantError("Failed to export data") from err
        _LOGGER.info("HAGym: exported data to %s", export_path)
        return export_path

    # ------------------------------------------------------------------
    # Workout lifecycle
    # ------------------------------------------------------------------

    async def start_workout(
        self, context_user_id: str | None = None, force: bool = False
    ) -> None:
        """Transition workout state to active."""
        user_id = await self.resolve_user_id(context_user_id)
        self._expire_confirmation_if_needed(notify=False)

        if (
            self._workout_state == STATE_ACTIVE
            and self._current_workout_id is not None
            and self._current_workout_user_id == user_id
        ):
            self._clear_pending_confirmation(notify=False)
            _LOGGER.debug("HAGym: start_workout ignored (already active for %s)", user_id)
            return

        if not force and not self._is_pending_confirmation(_CONFIRM_ACTION_START):
            self._set_pending_confirmation(_CONFIRM_ACTION_START)
            _LOGGER.debug(
                "HAGym: start workout confirmation pending for user %s (%ss timeout)",
                user_id,
                self._confirmation_timeout_seconds,
            )
            self._notify_listeners()
            return

        self._clear_pending_confirmation(notify=False)
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
            _LOGGER.exception("HAGym: failed to start workout in SQLite")
            raise HomeAssistantError("Failed to start workout") from err

        self._workout_state = STATE_ACTIVE
        self._reset_live_input_state()
        self._active_equipment_is_idle = True
        self._last_set_summary = None
        self._last_saved_set = None
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()

    async def finish_workout(
        self, context_user_id: str | None = None, force: bool = False
    ) -> None:
        """Transition workout state to ready for the resolved user."""
        user_id = await self.resolve_user_id(context_user_id)
        self._expire_confirmation_if_needed(notify=False)

        workout_is_active_for_user = (
            self._workout_state == STATE_ACTIVE
            and self._current_workout_id is not None
            and self._current_workout_user_id == user_id
        )
        open_workout = (
            await self._store.async_get_current_open_workout(user_id)
            if not workout_is_active_for_user
            else None
        )

        if not workout_is_active_for_user and open_workout is None:
            self._clear_pending_confirmation(notify=False)
            self._workout_state = STATE_READY
            self._reset_live_input_state()
            _LOGGER.debug("HAGym: finish_workout ignored (no active workout for %s)", user_id)
            self._notify_listeners()
            return

        if not force and not self._is_pending_confirmation(_CONFIRM_ACTION_FINISH):
            self._set_pending_confirmation(_CONFIRM_ACTION_FINISH)
            _LOGGER.debug(
                "HAGym: finish workout confirmation pending for user %s (%ss timeout)",
                user_id,
                self._confirmation_timeout_seconds,
            )
            self._notify_listeners()
            return

        self._clear_pending_confirmation(notify=False)

        try:
            workout_id_to_finish: int | None = None
            if workout_is_active_for_user:
                workout_id_to_finish = self._current_workout_id
            else:
                if open_workout is not None:
                    workout_id_to_finish = int(open_workout["id"])

            if workout_id_to_finish is not None:
                await self._store.async_finish_workout(workout_id_to_finish, _now_utc())
        except sqlite3.Error as err:
            _LOGGER.exception("HAGym: failed to finish workout in SQLite")
            raise HomeAssistantError("Failed to finish workout") from err

        if self._current_workout_user_id == user_id:
            self._workout_state = STATE_READY
            self._current_workout_id = None
            self._current_workout_started_at = None
            self._current_workout_user_id = None
            self._current_set_number = 0
            self._reset_live_input_state()

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
            _LOGGER.warning("HAGym save_current_set validation failed: %s", message)
            self.hass.async_create_task(
                self.hass.components.persistent_notification.async_create(
                    message=f"Cannot save set: {message}",
                    title="HAGym – Save Set",
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
            _LOGGER.warning("HAGym save_current_set_for_equipment validation failed: %s", message)
            self.hass.async_create_task(
                self.hass.components.persistent_notification.async_create(
                    message=f"Cannot save set: {message}",
                    title="HAGym – Save Set",
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

    async def async_save_current_activity(self, context_user_id: str | None = None) -> int:
        """Save one non-strength activity entry from current runtime inputs."""
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

        exercise_id = self._active_exercise_id
        metric_type = self.exercise_metric_type(exercise_id)
        errors = self._validate_current_activity_inputs(exercise_id=exercise_id, metric_type=metric_type)
        if errors:
            message = " ".join(errors)
            _LOGGER.warning("HAGym async_save_current_activity validation failed: %s", message)
            self.hass.async_create_task(
                self.hass.components.persistent_notification.async_create(
                    message=message,
                    title="HAGym - Save Activity",
                    notification_id="ha_fitness_save_activity_error",
                )
            )
            raise HomeAssistantError(message)

        duration_seconds = int(round(self._duration_minutes * 60.0)) if self._duration_minutes > 0 else None
        distance_m = round(self._distance_km * 1000.0, 3) if self._distance_km > 0 else None
        equipment_id = self._active_equipment_id
        if equipment_id == IDLE_EQUIPMENT_ID:
            equipment_id = None

        set_id = await self.async_save_activity(
            user_id=user_id,
            context_user_id=context_user_id,
            workout_id=self._current_workout_id,
            equipment_id=equipment_id,
            exercise_id=exercise_id,  # type: ignore[arg-type]
            metric_type=metric_type,
            reps=self._reps if metric_type == METRIC_TYPE_BODYWEIGHT else None,
            duration_seconds=duration_seconds,
            distance_m=distance_m,
            calories=self._calories if self._calories > 0 else None,
            steps=self._steps if self._steps > 0 else None,
            avg_heart_rate=self._avg_heart_rate if self._avg_heart_rate > 0 else None,
            max_heart_rate=self._max_heart_rate if self._max_heart_rate > 0 else None,
            intensity=self._intensity,
            notes=self._notes or None,
            added_weight=self._added_weight if self._added_weight > 0 else None,
        )

        self._duration_minutes = 0.0
        self._distance_km = 0.0
        self._calories = 0.0
        self._steps = 0
        self._avg_heart_rate = 0.0
        self._max_heart_rate = 0.0
        self._added_weight = 0.0
        self._intensity = _INTENSITY_MODERATE
        self._notify_listeners()
        return set_id

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
            exercise_id=exercise_id,
            weight=weight,
            reps=reps,
            require_active_workout=False,
            require_current_workout_id=False,
        )
        if errors:
            message = " ".join(errors)
            _LOGGER.warning("HAGym save_set validation failed: %s", message)
            self.hass.async_create_task(
                self.hass.components.persistent_notification.async_create(
                    message=f"Cannot save set: {message}",
                    title="HAGym – Save Set",
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
            _LOGGER.exception("HAGym: failed to save set via implicit workout")
            raise HomeAssistantError("Failed to save set") from err

        self._notify_listeners()

    async def async_save_activity(
        self,
        *,
        exercise_id: str,
        metric_type: str | None = None,
        user_id: str | None = None,
        workout_id: int | None = None,
        equipment_id: str | None = None,
        reps: int | None = None,
        duration_seconds: int | None = None,
        distance_m: float | None = None,
        calories: float | None = None,
        steps: int | None = None,
        avg_heart_rate: float | None = None,
        max_heart_rate: float | None = None,
        avg_power_watts: float | None = None,
        max_power_watts: float | None = None,
        avg_speed_mps: float | None = None,
        intensity: str | None = None,
        source: str | None = None,
        notes: str | None = None,
        created_at: datetime | None = None,
        added_weight: float | None = None,
        context_user_id: str | None = None,
    ) -> int:
        """Persist one non-strength activity entry."""
        resolved_user_id = (
            await self.resolve_user_id(user_id)
            if user_id is not None
            else await self.resolve_user_id(context_user_id)
        )
        exercise_row = self.get_exercise(exercise_id)
        if exercise_row is None:
            raise HomeAssistantError(f"Unknown exercise_id: {exercise_id}")
        if int(exercise_row.get("enabled", 1)) != 1:
            raise HomeAssistantError(f"Exercise is disabled: {exercise_id}")

        resolved_metric_type = (
            metric_type.strip().lower() if isinstance(metric_type, str) and metric_type.strip() else None
        )
        if resolved_metric_type is None:
            resolved_metric_type = self.exercise_metric_type(exercise_id)
        if resolved_metric_type not in SUPPORTED_METRIC_TYPES:
            raise HomeAssistantError(
                f"Unsupported metric_type '{resolved_metric_type}'. Supported values: {', '.join(SUPPORTED_METRIC_TYPES)}"
            )
        if resolved_metric_type == METRIC_TYPE_STRENGTH:
            raise HomeAssistantError(
                "Use save_current_set or add_set_to_workout for strength sets."
            )

        resolved_workout_id = workout_id
        if resolved_workout_id is not None:
            workout_row = await self._store.async_get_workout(int(resolved_workout_id))
            if workout_row is None:
                raise HomeAssistantError(f"Workout {resolved_workout_id} not found.")
        else:
            if (
                self._workout_state == STATE_ACTIVE
                and self._current_workout_user_id == resolved_user_id
                and self._current_workout_id is not None
            ):
                resolved_workout_id = self._current_workout_id
            else:
                open_workout = await self._store.async_get_current_open_workout(resolved_user_id)
                if open_workout is not None:
                    resolved_workout_id = int(open_workout["id"])

        created_value = created_at or _now_utc()
        cleanup_implicit_workout_id: int | None = None
        if resolved_workout_id is None:
            ended_at: datetime | None = None
            if duration_seconds is not None and duration_seconds > 0:
                ended_at = created_value + timedelta(seconds=int(duration_seconds))
            implicit_workout = await self._store.async_create_workout(
                user_id=resolved_user_id,
                started_at=created_value,
                ended_at=ended_at,
                notes=notes,
                status="completed",
            )
            resolved_workout_id = int(implicit_workout["id"])
            cleanup_implicit_workout_id = resolved_workout_id

        try:
            set_id = await self._store.async_save_activity_entry(
                user_id=resolved_user_id,
                workout_id=resolved_workout_id,
                exercise_id=exercise_id,
                metric_type=resolved_metric_type,
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
                created_at=created_value,
                added_weight=added_weight,
            )
        except (sqlite3.Error, ValueError) as err:
            _LOGGER.exception("HAGym: failed to save activity entry")
            raise HomeAssistantError(str(err)) from err

        if cleanup_implicit_workout_id is not None:
            # Keep the implicit workout as completed; nothing else required.
            _LOGGER.debug(
                "HAGym: created implicit completed workout %s for activity entry %s",
                cleanup_implicit_workout_id,
                set_id,
            )

        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()
        return set_id

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
        no_active_workout = require_active_workout and not self.is_workout_active
        if no_active_workout:
            errors.append(self._localized_text("Kein aktives Training.", "No active workout."))
        if require_current_workout_id and self._current_workout_id is None and not no_active_workout:
            errors.append(self._localized_text("Kein aktives Training.", "No active workout."))
        if not exercise_id or exercise_id == IDLE_EXERCISE_ID:
            errors.append(
                self._localized_text(
                    "Bitte zuerst eine Übung auswählen.",
                    "Please select an exercise first.",
                )
            )
        if weight < 0:
            errors.append(self._localized_text("Gewicht muss >= 0 sein.", "Weight must be >= 0."))
        if reps < 1:
            errors.append(
                self._localized_text(
                    "Wiederholungen müssen mindestens 1 sein.",
                    "Reps must be at least 1.",
                )
            )
        return errors

    def _validate_current_activity_inputs(
        self,
        *,
        exercise_id: str | None,
        metric_type: str,
    ) -> list[str]:
        """Validate live activity inputs and return user-facing error messages."""
        errors: list[str] = []
        if not self.is_workout_active or self._current_workout_id is None:
            errors.append(self._localized_text("Kein aktives Training.", "No active workout."))
        if not exercise_id or exercise_id == IDLE_EXERCISE_ID:
            errors.append(
                self._localized_text(
                    "Bitte zuerst eine Übung auswählen.",
                    "Please select an exercise first.",
                )
            )
            return errors
        if metric_type == METRIC_TYPE_STRENGTH:
            errors.append(
                self._localized_text(
                    "Diese Übung ist eine Kraftübung. Bitte Satz speichern verwenden.",
                    "This exercise is strength-based. Please use Save Set.",
                )
            )
            return errors

        has_duration = self._duration_minutes > 0
        has_distance = self._distance_km > 0
        has_reps = self._reps >= 1
        has_calories = self._calories > 0
        has_steps = self._steps > 0
        has_added_weight = self._added_weight > 0

        if metric_type in (METRIC_TYPE_DURATION, METRIC_TYPE_HOLD, METRIC_TYPE_CARDIO):
            if not has_duration:
                errors.append(
                    self._localized_text(
                        "Bitte eine Dauer eingeben.",
                        "Please enter a duration.",
                    )
                )
        elif metric_type == METRIC_TYPE_DISTANCE:
            if not has_distance:
                errors.append(
                    self._localized_text(
                        "Bitte eine Distanz eingeben.",
                        "Please enter a distance.",
                    )
                )
        elif metric_type == METRIC_TYPE_BODYWEIGHT:
            if not has_reps:
                errors.append(
                    self._localized_text(
                        "Wiederholungen müssen mindestens 1 sein.",
                        "Reps must be at least 1.",
                    )
                )
        elif metric_type == METRIC_TYPE_CUSTOM:
            if not any(
                (
                    has_duration,
                    has_distance,
                    has_calories,
                    has_steps,
                    has_reps,
                    has_added_weight,
                )
            ):
                errors.append(
                    self._localized_text(
                        "Bitte mindestens ein Aktivitätsfeld ausfüllen.",
                        "Please provide at least one activity field.",
                    )
                )

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
        if not exercise_id or exercise_id == IDLE_EXERCISE_ID:
            raise HomeAssistantError(
                self._localized_text(
                    "Bitte zuerst eine Übung auswählen.",
                    "Please select an exercise first.",
                )
            )
        metric_type = self.exercise_metric_type(exercise_id)
        if metric_type != METRIC_TYPE_STRENGTH:
            raise HomeAssistantError(
                "Selected exercise is not strength-based. Use save_activity for non-strength activities."
            )
        volume = weight * reps
        created_at = _now_utc()
        resolved_equipment_id = (
            selected_equipment_id
            if selected_equipment_id is not None
            else self._active_equipment_id or self.get_equipment_for_exercise(exercise_id)
        )
        if resolved_equipment_id == IDLE_EQUIPMENT_ID:
            resolved_equipment_id = None
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
                metric_type=metric_type,
            )
        except sqlite3.Error as err:
            _LOGGER.exception("HAGym: failed to write set to SQLite")
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
            "metric_type": metric_type,
            "equipment_id": resolved_equipment_id,
            "weight": weight,
            "reps": reps,
            "volume": volume,
            "notes": notes,
            "created_at": created_at.isoformat(),
        }
        _LOGGER.info("HAGym: %s (user=%s, notes=%s)", self._last_set_summary, user_id, notes)

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
                active_exercise_id = None
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


def _current_week_bounds(hass: HomeAssistant) -> tuple[str, str, str, str, str]:
    timezone_name = str(hass.config.time_zone or "UTC")
    try:
        local_tz = ZoneInfo(timezone_name)
    except Exception:
        timezone_name = "UTC"
        local_tz = ZoneInfo("UTC")

    now_local = datetime.now(local_tz)
    week_start = (now_local - timedelta(days=now_local.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_end = week_start + timedelta(days=7)
    return (
        timezone_name,
        week_start.isoformat(),
        week_end.isoformat(),
        week_start.astimezone(timezone.utc).isoformat(),
        week_end.astimezone(timezone.utc).isoformat(),
    )


def _weekly_ranges(
    hass: HomeAssistant, weeks: int = 12, max_weeks: int = 26
) -> tuple[str, list[dict[str, Any]]]:
    requested_weeks = max(1, min(int(weeks), int(max_weeks)))
    timezone_name = str(hass.config.time_zone or "UTC")
    try:
        local_tz = ZoneInfo(timezone_name)
    except Exception:
        timezone_name = "UTC"
        local_tz = ZoneInfo("UTC")

    now_local = datetime.now(local_tz)
    current_week_start = (now_local - timedelta(days=now_local.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    rows: list[dict[str, Any]] = []
    for offset in range(requested_weeks - 1, -1, -1):
        week_start = current_week_start - timedelta(days=7 * offset)
        week_end = week_start + timedelta(days=7)
        iso_year, iso_week, _ = week_start.isocalendar()
        rows.append(
            {
                "week_start_local": week_start.isoformat(),
                "week_end_local": week_end.isoformat(),
                "week_start_utc": week_start.astimezone(timezone.utc).isoformat(),
                "week_end_utc": week_end.astimezone(timezone.utc).isoformat(),
                "iso_year": int(iso_year),
                "iso_week": int(iso_week),
                "week_label": f"KW {int(iso_week):02d}",
                "timezone": timezone_name,
            }
        )
    return timezone_name, rows


def _safe_div(numerator: float, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def _duration_minutes(started_at: Any, ended_at: Any) -> float:
    started = _parse_datetime_utc(started_at)
    ended = _parse_datetime_utc(ended_at)
    if started is None or ended is None:
        return 0.0
    if ended < started:
        return 0.0
    return round((ended - started).total_seconds() / 60.0, 2)


def _parse_datetime_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _limit_rows(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return rows[: max(0, limit)]


def _build_training_balance(
    *,
    locale: str,
    user_id: str,
    week_start: str,
    week_end: str,
    muscle_groups: list[dict[str, Any]],
) -> dict[str, Any]:
    by_id: dict[str, float] = {
        str(row.get("muscle_group_id") or ""): float(row.get("volume", 0.0))
        for row in muscle_groups
        if row.get("muscle_group_id")
    }

    push_volume = sum(by_id.get(muscle_id, 0.0) for muscle_id in _PUSH_MUSCLE_GROUP_IDS)
    pull_volume = sum(by_id.get(muscle_id, 0.0) for muscle_id in _PULL_MUSCLE_GROUP_IDS)
    legs_volume = sum(by_id.get(muscle_id, 0.0) for muscle_id in _LEGS_MUSCLE_GROUP_IDS)
    core_volume = sum(by_id.get(muscle_id, 0.0) for muscle_id in _CORE_MUSCLE_GROUP_IDS)
    upper_body_volume = push_volume + pull_volume
    lower_body_volume = legs_volume
    categorized_volume = push_volume + pull_volume + legs_volume + core_volume

    if categorized_volume < 1.0:
        state = "insufficient_data"
    else:
        push_percent = (push_volume / categorized_volume) * 100.0
        pull_percent = (pull_volume / categorized_volume) * 100.0
        legs_percent = (legs_volume / categorized_volume) * 100.0
        missing_states: list[str] = []
        if push_percent < 15.0:
            missing_states.append("push_missing")
        if pull_percent < 15.0:
            missing_states.append("pull_missing")
        if legs_percent < 15.0:
            missing_states.append("legs_missing")

        if missing_states:
            priority = {"push_missing": 3, "pull_missing": 2, "legs_missing": 1}
            missing_states.sort(key=lambda item: priority.get(item, 0), reverse=True)
            state = missing_states[0]
        elif push_percent > 50.0:
            state = "push_heavy"
        elif pull_percent > 50.0:
            state = "pull_heavy"
        elif legs_percent > 50.0:
            state = "legs_heavy"
        elif (
            25.0 <= push_percent <= 45.0
            and 25.0 <= pull_percent <= 45.0
            and 25.0 <= legs_percent <= 45.0
        ):
            state = "balanced"
        else:
            state = "balanced"

    push_percent = (push_volume / categorized_volume) * 100.0 if categorized_volume > 0 else 0.0
    pull_percent = (pull_volume / categorized_volume) * 100.0 if categorized_volume > 0 else 0.0
    legs_percent = (legs_volume / categorized_volume) * 100.0 if categorized_volume > 0 else 0.0
    upper_body_percent = (
        (upper_body_volume / categorized_volume) * 100.0 if categorized_volume > 0 else 0.0
    )
    lower_body_percent = (
        (lower_body_volume / categorized_volume) * 100.0 if categorized_volume > 0 else 0.0
    )

    is_de = locale.lower().startswith("de")
    recommendation_map_en = {
        "insufficient_data": "Not enough training data this week yet.",
        "push_missing": "Push volume is still low this week.",
        "pull_missing": "Pull volume is still low this week.",
        "legs_missing": "Leg training is still missing this week.",
        "push_heavy": "Push volume dominates this week.",
        "pull_heavy": "Pull volume dominates this week.",
        "legs_heavy": "Leg volume dominates this week.",
        "balanced": "Very balanced training week.",
    }
    recommendation_map_de = {
        "insufficient_data": "Diese Woche sind noch zu wenige Trainingsdaten vorhanden.",
        "push_missing": "Diese Woche fehlt noch Push-Training.",
        "pull_missing": "Pull-Volumen ist diese Woche niedrig.",
        "legs_missing": "Diese Woche fehlt noch Beintraining.",
        "push_heavy": "Push-Volumen dominiert diese Woche.",
        "pull_heavy": "Pull-Volumen dominiert diese Woche.",
        "legs_heavy": "Bein-Volumen dominiert diese Woche.",
        "balanced": "Sehr ausgewogene Trainingswoche.",
    }

    recommendation = (
        recommendation_map_de.get(state, recommendation_map_de["balanced"])
        if is_de
        else recommendation_map_en.get(state, recommendation_map_en["balanced"])
    )
    return {
        "user_id": user_id,
        "week_start": week_start,
        "week_end": week_end,
        "push_volume": float(push_volume),
        "pull_volume": float(pull_volume),
        "legs_volume": float(legs_volume),
        "upper_body_volume": float(upper_body_volume),
        "lower_body_volume": float(lower_body_volume),
        "core_volume": float(core_volume),
        "push_percent": float(push_percent),
        "pull_percent": float(pull_percent),
        "legs_percent": float(legs_percent),
        "upper_body_percent": float(upper_body_percent),
        "lower_body_percent": float(lower_body_percent),
        "recommendation": recommendation,
        "categories": {
            "push": sorted(_PUSH_MUSCLE_GROUP_IDS),
            "pull": sorted(_PULL_MUSCLE_GROUP_IDS),
            "legs": sorted(_LEGS_MUSCLE_GROUP_IDS),
            "core": sorted(_CORE_MUSCLE_GROUP_IDS),
        },
        "categorized_volume_total": float(categorized_volume),
        "state": state,
    }
