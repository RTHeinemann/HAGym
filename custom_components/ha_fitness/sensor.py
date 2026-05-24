"""Sensor platform for HA Fitness Tracker."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, STATE_ACTIVE
from .coordinator import HAFitnessCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HA Fitness sensors from a config entry."""
    coordinator: HAFitnessCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            HAFitnessStatusSensor(coordinator, entry),
            HAFitnessActiveExerciseSensor(coordinator, entry),
            HAFitnessCurrentSetNumberSensor(coordinator, entry),
            HAFitnessLastSetSensor(coordinator, entry),
            HAFitnessCurrentSetVolumeSensor(coordinator, entry),
            HAFitnessActiveWorkoutSummarySensor(coordinator, entry),
        ]
    )


class _HAFitnessSensorBase(SensorEntity):
    """Base class for HA Fitness sensors."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=coordinator.display_name,
            manufacturer="HA Fitness",
            model="Fitness Tracker",
            entry_type="service",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


class HAFitnessStatusSensor(_HAFitnessSensorBase):
    """Sensor reporting current workout status."""

    _attr_translation_key = "status"

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str:
        return self._coordinator.workout_state


class HAFitnessActiveExerciseSensor(_HAFitnessSensorBase):
    """Sensor reporting the currently selected exercise."""

    _attr_translation_key = "active_exercise_sensor"

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_active_exercise_sensor"

    @property
    def native_value(self) -> str:
        return self._coordinator.active_exercise or "none"


class HAFitnessCurrentSetNumberSensor(_HAFitnessSensorBase):
    """Sensor reporting the current set number in the active workout."""

    _attr_translation_key = "current_set_number"

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_current_set_number"

    @property
    def native_value(self) -> int:
        return self._coordinator.current_set_number


class HAFitnessLastSetSensor(_HAFitnessSensorBase):
    """Sensor reporting the summary of the last saved set."""

    _attr_translation_key = "last_set"

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_set"

    @property
    def native_value(self) -> str:
        return self._coordinator.last_set_summary or "none"


class HAFitnessCurrentSetVolumeSensor(_HAFitnessSensorBase):
    """Sensor reporting weight × reps for the current set inputs."""

    _attr_translation_key = "current_set_volume"

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_current_set_volume"

    @property
    def native_value(self) -> float:
        return self._coordinator.weight * self._coordinator.reps


class HAFitnessActiveWorkoutSummarySensor(_HAFitnessSensorBase):
    """Sensor providing a full summary of the active workout state."""

    _attr_translation_key = "active_workout_summary"

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_active_workout_summary"

    @property
    def native_value(self) -> str:
        coord = self._coordinator
        if coord.workout_state != STATE_ACTIVE:
            return "inactive"
        return coord.active_exercise or "active"

    @property
    def extra_state_attributes(self) -> dict:
        coord = self._coordinator
        return {
            "workout_state": coord.workout_state,
            "active_exercise": coord.active_exercise,
            "weight": coord.weight,
            "reps": coord.reps,
            "notes": coord.notes,
            "current_set_number": coord.current_set_number,
            "current_set_volume": coord.weight * coord.reps,
            "last_set_summary": coord.last_set_summary,
        }

