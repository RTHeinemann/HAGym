"""Sensor platform for HAGym."""
from __future__ import annotations
from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LEGACY_USER_ID, STATE_ACTIVE
from .coordinator import HAFitnessCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HAGym sensors from a config entry."""
    coordinator: HAFitnessCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        HAFitnessStatusSensor(coordinator, entry),
        HAFitnessCurrentUserIdSensor(coordinator, entry),
        HAFitnessActiveExerciseSensor(coordinator, entry),
        HAFitnessCurrentSetNumberSensor(coordinator, entry),
        HAFitnessLastSetSensor(coordinator, entry),
        HAFitnessCurrentSetVolumeSensor(coordinator, entry),
        HAFitnessActiveWorkoutSummarySensor(coordinator, entry),
        HAFitnessTotalVolumeSensor(coordinator, entry),
        HAFitnessTotalSetsSensor(coordinator, entry),
        HAFitnessTotalWorkoutsSensor(coordinator, entry),
        HAFitnessRecentSetsSensor(coordinator, entry),
        HAFitnessPersonalTotalVolumeSensor(coordinator, entry),
        HAFitnessPersonalTotalSetsSensor(coordinator, entry),
        HAFitnessPersonalTotalWorkoutsSensor(coordinator, entry),
        HAFitnessPersonalRecentSetsSensor(coordinator, entry),
        HAFitnessHouseholdTotalVolumeSensor(coordinator, entry),
        HAFitnessHouseholdTotalSetsSensor(coordinator, entry),
        HAFitnessHouseholdTotalWorkoutsSensor(coordinator, entry),
        HAFitnessHouseholdRecentSetsSensor(coordinator, entry),
        HAFitnessPersonalWeeklySummarySensor(coordinator, entry),
        HAFitnessPersonalWeeklyExerciseStatisticsSensor(coordinator, entry),
        HAFitnessPersonalWeeklyMuscleGroupStatisticsSensor(coordinator, entry),
        HAFitnessPersonalTrainingBalanceSensor(coordinator, entry),
        HAFitnessHouseholdWeeklySummarySensor(coordinator, entry),
        HAFitnessExerciseCatalogSensor(coordinator, entry),
        HAFitnessExerciseStatisticsSensor(coordinator, entry),
        HAFitnessEquipmentCatalogSensor(coordinator, entry),
        HAFitnessEquipmentStatisticsSensor(coordinator, entry),
        HAFitnessMuscleGroupStatisticsSensor(coordinator, entry),
    ]

    for exercise_id in coordinator.enabled_exercise_ids:
        entities.append(HAFitnessPRByExerciseSensor(coordinator, entry, exercise_id))
        entities.append(HAFitnessVolumeByExerciseSensor(coordinator, entry, exercise_id))
        entities.append(HAFitnessPersonalPRByExerciseSensor(coordinator, entry, exercise_id))
        entities.append(HAFitnessPersonalVolumeByExerciseSensor(coordinator, entry, exercise_id))
        entities.append(HAFitnessHouseholdPRByExerciseSensor(coordinator, entry, exercise_id))
        entities.append(HAFitnessHouseholdVolumeByExerciseSensor(coordinator, entry, exercise_id))

    for equipment_id in coordinator.enabled_equipment_ids:
        entities.append(HAFitnessEquipmentLastSetSensor(coordinator, entry, equipment_id))
        entities.append(HAFitnessEquipmentPersonalVolumeSensor(coordinator, entry, equipment_id))
        entities.append(HAFitnessEquipmentHouseholdVolumeSensor(coordinator, entry, equipment_id))
        entities.append(HAFitnessEquipmentTotalVolumeSensor(coordinator, entry, equipment_id))
        entities.append(HAFitnessEquipmentTotalSetsSensor(coordinator, entry, equipment_id))

    for muscle_group_id in coordinator.enabled_muscle_group_ids:
        entities.append(HAFitnessMuscleGroupTotalVolumeSensor(coordinator, entry, muscle_group_id))
        entities.append(HAFitnessMuscleGroupPersonalVolumeSensor(coordinator, entry, muscle_group_id))
        entities.append(HAFitnessMuscleGroupHouseholdVolumeSensor(coordinator, entry, muscle_group_id))
        entities.append(HAFitnessMuscleGroupTotalSetsSensor(coordinator, entry, muscle_group_id))
        entities.append(HAFitnessMuscleGroupLastUsedSensor(coordinator, entry, muscle_group_id))
        entities.append(HAFitnessMuscleGroupTopExerciseSensor(coordinator, entry, muscle_group_id))

    async_add_entities(entities)


class _HAFitnessSensorBase(SensorEntity):
    """Base class for HAGym sensors."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=coordinator.display_name,
            manufacturer="HAGym",
            model="HAGym Tracker",
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


class HAFitnessCurrentUserIdSensor(_HAFitnessSensorBase):
    """Sensor for the currently resolved user id."""

    _attr_translation_key = "current_user_id"

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_current_user_id"

    @property
    def native_value(self) -> str:
        return self._coordinator.current_user_id or LEGACY_USER_ID


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
        return self._coordinator.active_exercise_display or "none"


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
    """Sensor providing a summary of the active workout state."""

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
        return coord.active_exercise_display or "active"

    @property
    def extra_state_attributes(self) -> dict:
        coord = self._coordinator
        return {
            "current_user_id": coord.current_user_id,
            "selected_user_id": coord.selected_user_id,
            "workout_state": coord.workout_state,
            "current_workout_id": coord.current_workout_id,
            "current_workout_started_at": coord.current_workout_started_at,
            "active_exercise": coord.active_exercise_display,
            "active_exercise_id": coord.active_exercise,
            "active_equipment": coord.active_equipment_display,
            "active_equipment_id": coord.active_equipment,
            "weight": coord.weight,
            "reps": coord.reps,
            "notes": coord.notes,
            "current_set_number": coord.current_set_number,
            "current_set_volume": coord.weight * coord.reps,
            "last_set_summary": coord.last_set_summary,
            "total_volume": coord.total_volume,
            "total_sets": coord.total_sets,
            "total_workouts": coord.total_workouts,
        }


class HAFitnessTotalVolumeSensor(_HAFitnessSensorBase):
    """Sensor for persisted total training volume (all users)."""

    _attr_translation_key = "total_volume"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_total_volume"

    @property
    def native_value(self) -> float:
        return self._coordinator.total_volume


class HAFitnessTotalSetsSensor(_HAFitnessSensorBase):
    """Sensor for persisted total set count (all users)."""

    _attr_translation_key = "total_sets"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_total_sets"

    @property
    def native_value(self) -> int:
        return self._coordinator.total_sets


class HAFitnessTotalWorkoutsSensor(_HAFitnessSensorBase):
    """Sensor for persisted total workout count (all users)."""

    _attr_translation_key = "total_workouts"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_total_workouts"

    @property
    def native_value(self) -> int:
        return self._coordinator.total_workouts


class HAFitnessRecentSetsSensor(_HAFitnessSensorBase):
    """Sensor exposing recent sets for dashboard cards (all users)."""

    _attr_translation_key = "recent_sets"

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_recent_sets"

    @property
    def native_value(self) -> int:
        return len(self._coordinator.recent_sets)

    @property
    def extra_state_attributes(self) -> dict:
        return {"recent_sets": self._coordinator.recent_sets}


class HAFitnessPersonalTotalVolumeSensor(_HAFitnessSensorBase):
    """Sensor for personal total volume."""

    _attr_translation_key = "personal_total_volume"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_personal_total_volume"

    @property
    def native_value(self) -> float:
        return self._coordinator.personal_total_volume


class HAFitnessPersonalTotalSetsSensor(_HAFitnessSensorBase):
    """Sensor for personal total sets."""

    _attr_translation_key = "personal_total_sets"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_personal_total_sets"

    @property
    def native_value(self) -> int:
        return self._coordinator.personal_total_sets


class HAFitnessPersonalTotalWorkoutsSensor(_HAFitnessSensorBase):
    """Sensor for personal total workouts."""

    _attr_translation_key = "personal_total_workouts"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_personal_total_workouts"

    @property
    def native_value(self) -> int:
        return self._coordinator.personal_total_workouts


class HAFitnessPersonalRecentSetsSensor(_HAFitnessSensorBase):
    """Sensor for personal recent set list."""

    _attr_translation_key = "personal_recent_sets"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_personal_recent_sets"

    @property
    def native_value(self) -> int:
        return len(self._coordinator.personal_recent_sets)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "selected_user_id": self._coordinator.selected_user_id,
            "recent_sets": self._coordinator.personal_recent_sets,
        }


class HAFitnessHouseholdTotalVolumeSensor(_HAFitnessSensorBase):
    """Sensor for household total volume."""

    _attr_translation_key = "household_total_volume"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_household_total_volume"

    @property
    def native_value(self) -> float:
        return self._coordinator.household_total_volume

    @property
    def extra_state_attributes(self) -> dict:
        return {"included_user_ids": self._coordinator.included_user_ids}


class HAFitnessHouseholdTotalSetsSensor(_HAFitnessSensorBase):
    """Sensor for household total sets."""

    _attr_translation_key = "household_total_sets"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_household_total_sets"

    @property
    def native_value(self) -> int:
        return self._coordinator.household_total_sets


class HAFitnessHouseholdTotalWorkoutsSensor(_HAFitnessSensorBase):
    """Sensor for household total workouts."""

    _attr_translation_key = "household_total_workouts"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_household_total_workouts"

    @property
    def native_value(self) -> int:
        return self._coordinator.household_total_workouts


class HAFitnessHouseholdRecentSetsSensor(_HAFitnessSensorBase):
    """Sensor for household recent set list."""

    _attr_translation_key = "household_recent_sets"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_household_recent_sets"

    @property
    def native_value(self) -> int:
        return len(self._coordinator.household_recent_sets)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "included_user_ids": self._coordinator.included_user_ids,
            "recent_sets": self._coordinator.household_recent_sets,
        }


class HAFitnessPersonalWeeklySummarySensor(_HAFitnessSensorBase):
    _attr_translation_key = "personal_weekly_summary"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_personal_weekly_summary"

    @property
    def native_value(self) -> float:
        return float(self._coordinator.get_personal_weekly_summary().get("total_volume", 0.0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self._coordinator.get_personal_weekly_summary())


class HAFitnessPersonalWeeklyExerciseStatisticsSensor(_HAFitnessSensorBase):
    _attr_translation_key = "personal_weekly_exercise_statistics"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = (
            f"{entry.entry_id}_personal_weekly_exercise_statistics"
        )

    @property
    def native_value(self) -> int:
        payload = self._coordinator.get_personal_weekly_exercise_statistics()
        return int(payload.get("exercise_count", len(list(payload.get("exercises", [])))))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self._coordinator.get_personal_weekly_exercise_statistics())


class HAFitnessPersonalWeeklyMuscleGroupStatisticsSensor(_HAFitnessSensorBase):
    _attr_translation_key = "personal_weekly_muscle_group_statistics"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = (
            f"{entry.entry_id}_personal_weekly_muscle_group_statistics"
        )

    @property
    def native_value(self) -> float:
        return float(
            self._coordinator.get_personal_weekly_muscle_group_statistics().get(
                "total_volume", 0.0
            )
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self._coordinator.get_personal_weekly_muscle_group_statistics())


class HAFitnessPersonalTrainingBalanceSensor(_HAFitnessSensorBase):
    _attr_translation_key = "personal_training_balance"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_personal_training_balance"

    @property
    def native_value(self) -> str:
        return str(
            self._coordinator.get_personal_training_balance().get(
                "state", "insufficient_data"
            )
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        balance = dict(self._coordinator.get_personal_training_balance())
        balance.pop("state", None)
        return balance


class HAFitnessHouseholdWeeklySummarySensor(_HAFitnessSensorBase):
    _attr_translation_key = "household_weekly_summary"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_household_weekly_summary"

    @property
    def native_value(self) -> float:
        return float(self._coordinator.get_household_weekly_summary().get("total_volume", 0.0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self._coordinator.get_household_weekly_summary())


class HAFitnessExerciseCatalogSensor(_HAFitnessSensorBase):
    """Sensor exposing full exercise catalog for dashboard/debug use."""

    _attr_translation_key = "exercise_catalog"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_exercise_catalog"

    @property
    def native_value(self) -> int:
        return len(
            [row for row in self._coordinator.exercises if int(row.get("enabled", 1)) == 1]
        )

    @property
    def extra_state_attributes(self) -> dict:
        exercises = [_exercise_row_payload(self._coordinator, row) for row in self._coordinator.exercises]
        enabled_exercises = [row for row in exercises if row["enabled"]]
        disabled_exercises = [row for row in exercises if not row["enabled"]]
        return {
            "exercises": exercises,
            "enabled_exercises": enabled_exercises,
            "disabled_exercises": disabled_exercises,
        }


class HAFitnessExerciseStatisticsSensor(_HAFitnessSensorBase):
    """Sensor exposing grouped per-exercise global/personal/household stats."""

    _attr_translation_key = "exercise_statistics"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_exercise_statistics"

    @property
    def native_value(self) -> int:
        return len(self._coordinator.exercise_statistics)

    @property
    def extra_state_attributes(self) -> dict:
        return {"by_exercise": self._coordinator.exercise_statistics}


class HAFitnessEquipmentCatalogSensor(_HAFitnessSensorBase):
    """Sensor exposing full equipment catalog."""

    _attr_translation_key = "equipment_catalog"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_equipment_catalog"

    @property
    def native_value(self) -> int:
        return len([row for row in self._coordinator.equipment if int(row.get("enabled", 1)) == 1])

    @property
    def extra_state_attributes(self) -> dict:
        rows = [_equipment_row_payload(row) for row in self._coordinator.equipment]
        enabled_rows = [row for row in rows if row["enabled"]]
        disabled_rows = [row for row in rows if not row["enabled"]]
        exercise_mapping: dict[str, list[str]] = {}
        for exercise in self._coordinator.exercises:
            equipment_id = str(exercise.get("equipment_id") or "")
            if not equipment_id:
                continue
            exercise_mapping.setdefault(equipment_id, []).append(str(exercise.get("id") or ""))
        return {
            "equipment": rows,
            "enabled_equipment": enabled_rows,
            "disabled_equipment": disabled_rows,
            "exercise_mapping": exercise_mapping,
        }


class HAFitnessEquipmentStatisticsSensor(_HAFitnessSensorBase):
    """Sensor exposing grouped per-equipment global/personal/household stats."""

    _attr_translation_key = "equipment_statistics"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_equipment_statistics"

    @property
    def native_value(self) -> int:
        return len(
            [
                row
                for row in self._coordinator.equipment_statistics
                if int(row.get("total_sets", 0)) > 0
            ]
        )

    @property
    def extra_state_attributes(self) -> dict:
        return {"by_equipment": self._coordinator.equipment_statistics}


class HAFitnessMuscleGroupStatisticsSensor(_HAFitnessSensorBase):
    """Sensor exposing grouped per-muscle-group global/personal/household stats."""

    _attr_translation_key = "muscle_group_statistics"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_muscle_group_statistics"

    @property
    def native_value(self) -> int:
        return len(
            [
                row
                for row in self._coordinator.muscle_group_statistics
                if float(row.get("total_volume", 0.0)) > 0.0
            ]
        )

    @property
    def extra_state_attributes(self) -> dict:
        return {"by_muscle_group": self._coordinator.muscle_group_statistics}


class _HAFitnessMuscleGroupSensorBase(SensorEntity):
    """Base class for muscle-group-specific sensors."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, muscle_group_id: str
    ) -> None:
        self._coordinator = coordinator
        self._muscle_group_id = muscle_group_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id, "muscle_group", muscle_group_id)},
            name=coordinator.muscle_group_display_name(muscle_group_id),
            manufacturer="HAGym",
            model="HAGym Muscle Group",
            via_device=(DOMAIN, entry.entry_id),
            entry_type="service",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        row = self._coordinator.get_muscle_group(self._muscle_group_id)
        if row is None:
            return False
        return int(row.get("enabled", 1)) == 1

    def _stats(self) -> dict[str, Any]:
        return self._coordinator.get_muscle_group_statistics(self._muscle_group_id)


class HAFitnessMuscleGroupTotalVolumeSensor(_HAFitnessMuscleGroupSensorBase):
    _attr_translation_key = "total_volume"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, muscle_group_id: str) -> None:
        super().__init__(coordinator, entry, muscle_group_id)
        self._attr_unique_id = f"{entry.entry_id}_{muscle_group_id}_total_volume"

    @property
    def native_value(self) -> float:
        return float(self._stats().get("total_volume", 0.0))


class HAFitnessMuscleGroupPersonalVolumeSensor(_HAFitnessMuscleGroupSensorBase):
    _attr_translation_key = "personal_total_volume"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, muscle_group_id: str) -> None:
        super().__init__(coordinator, entry, muscle_group_id)
        self._attr_unique_id = f"{entry.entry_id}_{muscle_group_id}_personal_total_volume"

    @property
    def native_value(self) -> float:
        return float(self._stats().get("personal_volume", 0.0))


class HAFitnessMuscleGroupHouseholdVolumeSensor(_HAFitnessMuscleGroupSensorBase):
    _attr_translation_key = "household_total_volume"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, muscle_group_id: str) -> None:
        super().__init__(coordinator, entry, muscle_group_id)
        self._attr_unique_id = f"{entry.entry_id}_{muscle_group_id}_household_total_volume"

    @property
    def native_value(self) -> float:
        return float(self._stats().get("household_volume", 0.0))


class HAFitnessMuscleGroupTotalSetsSensor(_HAFitnessMuscleGroupSensorBase):
    _attr_translation_key = "total_sets"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, muscle_group_id: str) -> None:
        super().__init__(coordinator, entry, muscle_group_id)
        self._attr_unique_id = f"{entry.entry_id}_{muscle_group_id}_total_sets"

    @property
    def native_value(self) -> int:
        return int(self._stats().get("total_sets", 0))


class HAFitnessMuscleGroupLastUsedSensor(_HAFitnessMuscleGroupSensorBase):
    _attr_translation_key = "last_used"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, muscle_group_id: str) -> None:
        super().__init__(coordinator, entry, muscle_group_id)
        self._attr_unique_id = f"{entry.entry_id}_{muscle_group_id}_last_used"

    @property
    def native_value(self) -> str | None:
        value = self._stats().get("last_used")
        return str(value) if value else None


class HAFitnessMuscleGroupTopExerciseSensor(_HAFitnessMuscleGroupSensorBase):
    _attr_translation_key = "top_exercise"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, muscle_group_id: str) -> None:
        super().__init__(coordinator, entry, muscle_group_id)
        self._attr_unique_id = f"{entry.entry_id}_{muscle_group_id}_top_exercise"

    @property
    def native_value(self) -> str:
        top_exercise = self._stats().get("top_exercise")
        if not isinstance(top_exercise, dict):
            return "none"
        exercise_id = str(top_exercise.get("exercise_id") or "")
        if not exercise_id:
            return "none"
        return self._coordinator.exercise_display_name(exercise_id)

    @property
    def extra_state_attributes(self) -> dict:
        top_exercise = self._stats().get("top_exercise")
        return {"top_exercise": top_exercise} if isinstance(top_exercise, dict) else {}


class _HAFitnessEquipmentSensorBase(SensorEntity):
    """Base class for equipment-specific sensors."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, equipment_id: str
    ) -> None:
        self._coordinator = coordinator
        self._equipment_id = equipment_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id, equipment_id)},
            name=coordinator.equipment_display_name(equipment_id),
            manufacturer="HAGym",
            model="HAGym Equipment",
            suggested_area=coordinator.equipment_location(equipment_id),
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

    @property
    def available(self) -> bool:
        return self._coordinator.equipment_enabled(self._equipment_id)


class HAFitnessEquipmentLastSetSensor(_HAFitnessEquipmentSensorBase):
    """Sensor reporting last set summary for one equipment runtime state."""

    _attr_translation_key = "last_set"

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, equipment_id: str
    ) -> None:
        super().__init__(coordinator, entry, equipment_id)
        self._attr_unique_id = f"{entry.entry_id}_{equipment_id}_last_set"

    @property
    def native_value(self) -> str:
        return self._coordinator.get_equipment_last_set_summary(self._equipment_id) or "none"


class HAFitnessEquipmentPersonalVolumeSensor(_HAFitnessEquipmentSensorBase):
    """Sensor for personal volume total on one equipment."""

    _attr_translation_key = "personal_total_volume"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, equipment_id: str
    ) -> None:
        super().__init__(coordinator, entry, equipment_id)
        self._attr_unique_id = f"{entry.entry_id}_{equipment_id}_personal_total_volume"

    @property
    def native_value(self) -> float:
        return self._coordinator.get_equipment_personal_volume(self._equipment_id)


class HAFitnessEquipmentHouseholdVolumeSensor(_HAFitnessEquipmentSensorBase):
    """Sensor for household volume total on one equipment."""

    _attr_translation_key = "household_total_volume"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, equipment_id: str
    ) -> None:
        super().__init__(coordinator, entry, equipment_id)
        self._attr_unique_id = f"{entry.entry_id}_{equipment_id}_household_total_volume"

    @property
    def native_value(self) -> float:
        return self._coordinator.get_equipment_household_volume(self._equipment_id)


class HAFitnessEquipmentTotalVolumeSensor(_HAFitnessEquipmentSensorBase):
    """Sensor for global total volume on one equipment."""

    _attr_translation_key = "total_volume"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, equipment_id: str
    ) -> None:
        super().__init__(coordinator, entry, equipment_id)
        self._attr_unique_id = f"{entry.entry_id}_{equipment_id}_total_volume"

    @property
    def native_value(self) -> float:
        return self._coordinator.get_equipment_total_volume(self._equipment_id)


class HAFitnessEquipmentTotalSetsSensor(_HAFitnessEquipmentSensorBase):
    """Sensor for global total set count on one equipment."""

    _attr_translation_key = "total_sets"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, equipment_id: str
    ) -> None:
        super().__init__(coordinator, entry, equipment_id)
        self._attr_unique_id = f"{entry.entry_id}_{equipment_id}_total_sets"

    @property
    def native_value(self) -> int:
        return self._coordinator.get_equipment_total_sets(self._equipment_id)


class _ExerciseMetricSensor(SensorEntity):
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HAFitnessCoordinator,
        entry: ConfigEntry,
        exercise: str,
        *,
        translation_key: str,
        unique_prefix: str,
        value_getter: Callable[[str], float],
    ) -> None:
        exercise_key = _exercise_key(exercise)
        self._coordinator = coordinator
        self._exercise = exercise
        self._value_getter = value_getter
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id, "exercise", exercise_key)},
            name=coordinator.exercise_display_name(exercise),
            manufacturer="HAGym",
            model="HAGym Exercise",
            via_device=(DOMAIN, entry.entry_id),
            entry_type="service",
        )
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{entry.entry_id}_{unique_prefix}_{exercise_key}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._coordinator.exercise_enabled(self._exercise)

    @property
    def native_value(self) -> float:
        return self._value_getter(self._exercise)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attributes = self._coordinator.get_exercise_muscle_group_attributes(
            self._exercise
        )
        attributes["exercise_id"] = self._exercise
        return attributes


class HAFitnessPRByExerciseSensor(_ExerciseMetricSensor):
    """Sensor for per-exercise PR based on max saved weight (all users)."""

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, exercise: str) -> None:
        super().__init__(
            coordinator,
            entry,
            exercise,
            translation_key="exercise_pr",
            unique_prefix="pr",
            value_getter=coordinator.get_pr_by_exercise,
        )


class HAFitnessVolumeByExerciseSensor(_ExerciseMetricSensor):
    """Sensor for per-exercise accumulated total volume (all users)."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, exercise: str) -> None:
        super().__init__(
            coordinator,
            entry,
            exercise,
            translation_key="exercise_total_volume",
            unique_prefix="volume",
            value_getter=coordinator.get_volume_by_exercise,
        )
        self._attr_unique_id = f"{entry.entry_id}_volume_{_exercise_key(exercise)}_total"


class HAFitnessPersonalPRByExerciseSensor(_ExerciseMetricSensor):
    """Sensor for personal per-exercise PR."""

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, exercise: str) -> None:
        super().__init__(
            coordinator,
            entry,
            exercise,
            translation_key="exercise_personal_pr",
            unique_prefix="personal_pr",
            value_getter=coordinator.get_personal_pr_by_exercise,
        )


class HAFitnessPersonalVolumeByExerciseSensor(_ExerciseMetricSensor):
    """Sensor for personal per-exercise volume total."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, exercise: str) -> None:
        super().__init__(
            coordinator,
            entry,
            exercise,
            translation_key="exercise_personal_total_volume",
            unique_prefix="personal_volume",
            value_getter=coordinator.get_personal_volume_by_exercise,
        )
        self._attr_unique_id = f"{entry.entry_id}_personal_volume_{_exercise_key(exercise)}_total"


class HAFitnessHouseholdPRByExerciseSensor(_ExerciseMetricSensor):
    """Sensor for household per-exercise PR."""

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, exercise: str) -> None:
        super().__init__(
            coordinator,
            entry,
            exercise,
            translation_key="exercise_household_pr",
            unique_prefix="household_pr",
            value_getter=coordinator.get_household_pr_by_exercise,
        )


class HAFitnessHouseholdVolumeByExerciseSensor(_ExerciseMetricSensor):
    """Sensor for household per-exercise volume total."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry, exercise: str) -> None:
        super().__init__(
            coordinator,
            entry,
            exercise,
            translation_key="exercise_household_total_volume",
            unique_prefix="household_volume",
            value_getter=coordinator.get_household_volume_by_exercise,
        )
        self._attr_unique_id = f"{entry.entry_id}_household_volume_{_exercise_key(exercise)}_total"


def _exercise_key(exercise: str) -> str:
    return exercise.lower().replace(" ", "_").replace("-", "_")


def _exercise_row_payload(
    coordinator: HAFitnessCoordinator, row: dict[str, Any]
) -> dict[str, Any]:
    """Build normalized exercise catalog payload row with localized display name."""
    exercise_id = str(row.get("id") or "")
    return {
        "id": exercise_id,
        "display_name": coordinator.exercise_display_name(exercise_id),
        "name_en": row.get("name_en"),
        "name_de": row.get("name_de"),
        "muscle_group": row.get("muscle_group"),
        "equipment": row.get("equipment"),
        "equipment_id": row.get("equipment_id"),
        "enabled": int(row.get("enabled", 1)) == 1,
        "sort_order": int(row.get("sort_order", 0)),
        "created_at": row.get("created_at"),
    }


def _equipment_row_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "name": row.get("name"),
        "description": row.get("description"),
        "icon": row.get("icon"),
        "location": row.get("location"),
        "enabled": int(row.get("enabled", 1)) == 1,
        "sort_order": int(row.get("sort_order", 100)),
        "created_at": row.get("created_at"),
    }
