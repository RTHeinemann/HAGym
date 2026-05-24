"""HA Fitness Tracker coordinator."""
from __future__ import annotations

import logging
from collections.abc import Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import STATE_ACTIVE, STATE_READY

_LOGGER = logging.getLogger(__name__)


class HAFitnessCoordinator:
    """Manages runtime state for the HA Fitness integration."""

    def __init__(self, hass: HomeAssistant, display_name: str) -> None:
        self.hass = hass
        self.display_name = display_name
        self._workout_state: str = STATE_READY
        self._active_exercise: str | None = None
        self._weight: float = 0.0
        self._reps: int = 0
        self._notes: str = ""
        self._current_set_number: int = 0
        self._last_set_summary: str | None = None
        self._last_saved_set: dict | None = None
        self._listeners: list[Callable[[], None]] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Listener management
    # ------------------------------------------------------------------

    @callback
    def async_add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """Register a listener that is called on state changes. Returns an unsubscribe function."""
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
    # Workout lifecycle
    # ------------------------------------------------------------------

    def start_workout(self) -> None:
        """Transition workout state to active."""
        _LOGGER.info("HA Fitness: workout started")
        self._workout_state = STATE_ACTIVE
        self._current_set_number = 0
        self._last_set_summary = None
        self._last_saved_set = None
        self._notes = ""
        self._notify_listeners()

    def finish_workout(self) -> None:
        """Transition workout state to ready.

        active_exercise is intentionally retained so the user can quickly
        resume with the same exercise in the next workout session.
        """
        _LOGGER.info("HA Fitness: workout finished")
        self._workout_state = STATE_READY
        self._notify_listeners()

    # ------------------------------------------------------------------
    # Set saving
    # ------------------------------------------------------------------

    def save_current_set(self) -> None:
        """Save a set using the current runtime state with validation.

        Raises HomeAssistantError if validation fails.
        """
        errors: list[str] = []

        if self._workout_state != STATE_ACTIVE:
            errors.append("No active workout. Press Start Workout first.")
        if not self._active_exercise:
            errors.append("No exercise selected.")
        if self._weight <= 0:
            errors.append("Weight must be greater than 0.")
        if self._reps <= 0:
            errors.append("Reps must be greater than 0.")

        if errors:
            message = " ".join(errors)
            _LOGGER.warning("HA Fitness save_current_set validation failed: %s", message)
            self.hass.components.persistent_notification.async_create(
                message=f"Cannot save set: {message}",
                title="HA Fitness – Save Set",
                notification_id="ha_fitness_save_set_error",
            )
            raise HomeAssistantError(message)

        self._do_save_set(
            exercise=self._active_exercise,  # type: ignore[arg-type]
            weight=self._weight,
            reps=self._reps,
            notes=self._notes or None,
        )

    def save_set(
        self,
        exercise: str,
        weight: float,
        reps: int,
        notes: str | None = None,
    ) -> None:
        """Save a set with explicitly provided data (used by the service call).

        Raises HomeAssistantError if validation fails.
        """
        errors: list[str] = []

        if not exercise:
            errors.append("Exercise must not be empty.")
        if weight <= 0:
            errors.append("Weight must be greater than 0.")
        if reps <= 0:
            errors.append("Reps must be greater than 0.")

        if errors:
            message = " ".join(errors)
            _LOGGER.warning("HA Fitness save_set validation failed: %s", message)
            self.hass.components.persistent_notification.async_create(
                message=f"Cannot save set: {message}",
                title="HA Fitness – Save Set",
                notification_id="ha_fitness_save_set_error",
            )
            raise HomeAssistantError(message)

        self._do_save_set(exercise=exercise, weight=weight, reps=reps, notes=notes)

    def _do_save_set(
        self,
        exercise: str,
        weight: float,
        reps: int,
        notes: str | None,
    ) -> None:
        """Persist set into runtime state and notify listeners."""
        self._current_set_number += 1
        self._last_set_summary = (
            f"Set {self._current_set_number}: {exercise} - {weight} kg x {reps}"
        )
        self._last_saved_set = {
            "set_number": self._current_set_number,
            "exercise": exercise,
            "weight": weight,
            "reps": reps,
            "notes": notes,
        }
        _LOGGER.info(
            "HA Fitness: %s (notes=%s)",
            self._last_set_summary,
            notes,
        )
        self._notify_listeners()
