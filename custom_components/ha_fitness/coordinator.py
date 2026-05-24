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

from .const import EXERCISES, STATE_ACTIVE, STATE_READY
from .storage import HAFitnessStore

_LOGGER = logging.getLogger(__name__)


class HAFitnessCoordinator:
    """Manages runtime state for the HA Fitness integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        display_name: str,
        store: HAFitnessStore,
    ) -> None:
        self.hass = hass
        self.display_name = display_name
        self._store = store

        self._current_workout_id: int | None = None
        self._current_workout_started_at: str | None = None
        self._workout_state: str = STATE_READY
        self._active_exercise: str | None = None
        self._weight: float = 0.0
        self._reps: int = 0
        self._notes: str = ""
        self._current_set_number: int = 0
        self._last_set_summary: str | None = None
        self._last_saved_set: dict | None = None
        self._total_volume: float = 0.0
        self._total_sets: int = 0
        self._total_workouts: int = 0
        self._recent_sets: list[dict[str, Any]] = []
        self._pr_by_exercise: dict[str, float] = {exercise: 0.0 for exercise in EXERCISES}
        self._volume_by_exercise: dict[str, float] = {
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
    def last_saved_set(self) -> dict | None:
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

    def get_pr_by_exercise(self, exercise: str) -> float:
        return self._pr_by_exercise.get(exercise, 0.0)

    def get_volume_by_exercise(self, exercise: str) -> float:
        return self._volume_by_exercise.get(exercise, 0.0)

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

    # ------------------------------------------------------------------
    # Startup and statistics
    # ------------------------------------------------------------------

    async def async_initialize(self) -> None:
        """Restore persisted state on integration startup."""
        try:
            open_workout = await self._store.async_get_current_open_workout()
            if open_workout is not None:
                self._current_workout_id = int(open_workout["id"])
                self._current_workout_started_at = str(open_workout["started_at"])
                self._workout_state = STATE_ACTIVE
                self._current_set_number = await self._store.async_get_set_count_for_workout(
                    self._current_workout_id
                )
            else:
                self._current_workout_id = None
                self._current_workout_started_at = None
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

    async def async_refresh_statistics(self, notify: bool = True) -> None:
        """Refresh cached statistics from SQLite."""
        try:
            self._total_volume = await self._store.async_get_total_volume()
            self._total_sets = await self._store.async_get_set_count()
            self._total_workouts = await self._store.async_get_workout_count()
            self._recent_sets = await self._store.async_get_recent_sets(10)

            for exercise in EXERCISES:
                self._pr_by_exercise[exercise] = await self._store.async_get_pr_by_exercise(
                    exercise
                )
                self._volume_by_exercise[
                    exercise
                ] = await self._store.async_get_total_volume_by_exercise(exercise)
        except sqlite3.Error as err:
            _LOGGER.exception("HA Fitness: failed to refresh statistics")
            raise HomeAssistantError("Failed to refresh statistics") from err

        if notify:
            self._notify_listeners()

    async def async_export_data(self) -> str:
        """Export statistics and recent sets to JSON in /config/ha_fitness."""
        await self.async_refresh_statistics(notify=False)
        payload = {
            "generated_at": _now_utc().isoformat(),
            "total_volume": self._total_volume,
            "total_sets": self._total_sets,
            "total_workouts": self._total_workouts,
            "pr_by_exercise": self._pr_by_exercise,
            "volume_by_exercise": self._volume_by_exercise,
            "recent_sets": self._recent_sets,
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

    async def start_workout(self) -> None:
        """Transition workout state to active."""
        if self._workout_state == STATE_ACTIVE and self._current_workout_id is not None:
            _LOGGER.debug("HA Fitness: start_workout ignored (already active)")
            return

        started_at = _now_utc()
        try:
            self._current_workout_id = await self._store.async_start_workout(started_at)
        except sqlite3.Error as err:
            _LOGGER.exception("HA Fitness: failed to start workout in SQLite")
            raise HomeAssistantError("Failed to start workout") from err

        self._current_workout_started_at = started_at.isoformat()
        self._workout_state = STATE_ACTIVE
        self._current_set_number = 0
        self._last_set_summary = None
        self._last_saved_set = None
        self._notes = ""
        self._notify_listeners()

    async def finish_workout(self) -> None:
        """Transition workout state to ready."""
        if self._workout_state == STATE_ACTIVE and self._current_workout_id is not None:
            try:
                await self._store.async_finish_workout(self._current_workout_id, _now_utc())
            except sqlite3.Error as err:
                _LOGGER.exception("HA Fitness: failed to finish workout in SQLite")
                raise HomeAssistantError("Failed to finish workout") from err

        self._workout_state = STATE_READY
        self._current_workout_id = None
        self._current_workout_started_at = None
        await self.async_refresh_statistics(notify=False)
        self._notify_listeners()

    # ------------------------------------------------------------------
    # Set saving
    # ------------------------------------------------------------------

    async def save_current_set(self) -> None:
        """Save a set using the current runtime state with validation."""
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
    ) -> None:
        """Save a set with explicitly provided data (used by service call)."""
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

        if self._workout_state == STATE_ACTIVE and self._current_workout_id is not None:
            await self._persist_set(
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

        # Implicit workout flow for explicit service calls when inactive:
        # create workout -> save one set -> finish workout.
        try:
            workout_id = await self._store.async_start_workout(_now_utc())
            await self._persist_set(
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
            "workout_id": workout_id,
            "set_number": set_number,
            "exercise": exercise,
            "weight": weight,
            "reps": reps,
            "volume": volume,
            "notes": notes,
            "created_at": created_at.isoformat(),
        }
        _LOGGER.info("HA Fitness: %s (notes=%s)", self._last_set_summary, notes)

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
