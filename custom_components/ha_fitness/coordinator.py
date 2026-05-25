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

from .const import EXERCISES, LEGACY_USER_ID, STATE_ACTIVE, STATE_READY
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
        self._active_exercise: str | None = None
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
        self._pr_by_exercise: dict[str, float] = {exercise: 0.0 for exercise in EXERCISES}
        self._volume_by_exercise: dict[str, float] = {
            exercise: 0.0 for exercise in EXERCISES
        }

        self._current_user_id: str | None = None
        self._selected_user_id: str | None = None
        self._users: list[dict[str, Any]] = []
        self._personal_total_volume: float = 0.0
        self._personal_total_sets: int = 0
        self._personal_total_workouts: int = 0
        self._personal_recent_sets: list[dict[str, Any]] = []
        self._personal_pr_by_exercise: dict[str, float] = {
            exercise: 0.0 for exercise in EXERCISES
        }
        self._personal_volume_by_exercise: dict[str, float] = {
            exercise: 0.0 for exercise in EXERCISES
        }

        self._household_total_volume: float = 0.0
        self._household_total_sets: int = 0
        self._household_total_workouts: int = 0
        self._household_recent_sets: list[dict[str, Any]] = []
        self._household_pr_by_exercise: dict[str, float] = {
            exercise: 0.0 for exercise in EXERCISES
        }
        self._household_volume_by_exercise: dict[str, float] = {
            exercise: 0.0 for exercise in EXERCISES
        }

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
        return self._active_exercise

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
    def included_user_ids(self) -> list[str] | None:
        return self._included_user_ids

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

    def set_active_exercise(self, exercise: str) -> None:
        """Update the currently selected exercise."""
        self._active_exercise = exercise
        _LOGGER.debug("HA Fitness: active exercise set to %s", exercise)
        self._notify_listeners()

    def set_weight(self, weight: float) -> None:
        """Update the current weight value."""
        self._weight = weight
        _LOGGER.debug("HA Fitness: weight set to %s", weight)
        self._notify_listeners()

    def set_reps(self, reps: int) -> None:
        """Update the current reps value."""
        self._reps = reps
        _LOGGER.debug("HA Fitness: reps set to %s", reps)
        self._notify_listeners()

    def set_notes(self, notes: str) -> None:
        """Update the current notes value."""
        self._notes = notes
        _LOGGER.debug("HA Fitness: notes updated")
        self._notify_listeners()

    async def set_selected_user(self, user_id: str | None) -> None:
        """Set selected user for personal dashboard statistics."""
        if user_id:
            resolved = await self.resolve_user_id(user_id)
            self._selected_user_id = resolved
        else:
            self._selected_user_id = None
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()

    # ------------------------------------------------------------------
    # Startup and statistics
    # ------------------------------------------------------------------

    async def async_initialize(self) -> None:
        """Restore persisted state on integration startup."""
        try:
            await self.resolve_user_id(None)
            await self.async_refresh_users()

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
                    exercise=str(last_set["exercise"]),
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
        display_name = context_user_id if context_user_id else resolved
        await self._store.async_upsert_user(resolved, display_name)

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

            for exercise in EXERCISES:
                self._pr_by_exercise[exercise] = await self._store.async_get_pr_by_exercise(exercise)
                self._volume_by_exercise[
                    exercise
                ] = await self._store.async_get_total_volume_by_exercise(exercise)

                self._personal_pr_by_exercise[exercise] = await self._store.async_get_pr_by_exercise(
                    exercise, personal_user_id
                )
                self._personal_volume_by_exercise[
                    exercise
                ] = await self._store.async_get_total_volume_by_exercise(
                    exercise, personal_user_id
                )

                self._household_pr_by_exercise[
                    exercise
                ] = await self._store.async_get_household_pr_by_exercise(
                    exercise, household_user_ids
                )
                self._household_volume_by_exercise[
                    exercise
                ] = await self._store.async_get_household_total_volume_by_exercise(
                    exercise, household_user_ids
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
            exercise=self._active_exercise,
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
            exercise=self._active_exercise,  # type: ignore[arg-type]
            weight=self._weight,
            reps=self._reps,
            notes=self._notes or None,
        )
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

        errors = self._validate_set_inputs(
            exercise=exercise,
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
                exercise=exercise,
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
                    exercise=exercise,
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
                    exercise=exercise,
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
        exercise: str | None,
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
        if not exercise:
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
        exercise: str,
        weight: float,
        reps: int,
        notes: str | None,
        refresh_stats: bool = True,
    ) -> None:
        volume = weight * reps
        created_at = _now_utc()
        try:
            set_id = await self._store.async_save_set(
                user_id=user_id,
                workout_id=workout_id,
                exercise=exercise,
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
            exercise=exercise,
            weight=weight,
            reps=reps,
        )
        self._last_saved_set = {
            "id": set_id,
            "user_id": user_id,
            "workout_id": workout_id,
            "set_number": set_number,
            "exercise": exercise,
            "weight": weight,
            "reps": reps,
            "volume": volume,
            "notes": notes,
            "created_at": created_at.isoformat(),
        }
        _LOGGER.info("HA Fitness: %s (user=%s, notes=%s)", self._last_set_summary, user_id, notes)

        if refresh_stats:
            await self.async_refresh_statistics(notify=False)

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
