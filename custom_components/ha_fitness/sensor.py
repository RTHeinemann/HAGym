"""Sensor platform for HAGym."""
from __future__ import annotations
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfMass, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    LEGACY_USER_ID,
    METRIC_TYPE_BODYWEIGHT,
    METRIC_TYPE_CARDIO,
    METRIC_TYPE_DISTANCE,
    METRIC_TYPE_DURATION,
    METRIC_TYPE_HOLD,
    METRIC_TYPE_STRENGTH,
)
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
        HAFitnessPersonalRecentWorkoutsSensor(coordinator, entry),
        HAFitnessHouseholdTotalVolumeSensor(coordinator, entry),
        HAFitnessHouseholdTotalSetsSensor(coordinator, entry),
        HAFitnessHouseholdTotalWorkoutsSensor(coordinator, entry),
        HAFitnessHouseholdRecentSetsSensor(coordinator, entry),
        HAFitnessCoreTotalSensor(
            coordinator, entry, scope="personal", metric_key="strength_volume"
        ),
        HAFitnessCoreTotalSensor(
            coordinator, entry, scope="personal", metric_key="activity_load"
        ),
        HAFitnessCoreTotalSensor(
            coordinator, entry, scope="personal", metric_key="duration_minutes"
        ),
        HAFitnessCoreTotalSensor(
            coordinator, entry, scope="personal", metric_key="distance_km"
        ),
        HAFitnessCoreTotalSensor(
            coordinator, entry, scope="personal", metric_key="reps"
        ),
        HAFitnessCoreTotalSensor(
            coordinator, entry, scope="personal", metric_key="sets"
        ),
        HAFitnessCoreTotalSensor(
            coordinator, entry, scope="household", metric_key="strength_volume"
        ),
        HAFitnessCoreTotalSensor(
            coordinator, entry, scope="household", metric_key="activity_load"
        ),
        HAFitnessCoreTotalSensor(
            coordinator, entry, scope="household", metric_key="duration_minutes"
        ),
        HAFitnessCoreTotalSensor(
            coordinator, entry, scope="household", metric_key="distance_km"
        ),
        HAFitnessCoreTotalSensor(
            coordinator, entry, scope="household", metric_key="reps"
        ),
        HAFitnessCoreTotalSensor(
            coordinator, entry, scope="household", metric_key="sets"
        ),
        HAFitnessPersonalDailyMetricStatisticsSensor(coordinator, entry),
        HAFitnessHouseholdDailyMetricStatisticsSensor(coordinator, entry),
        HAFitnessPersonalWeeklySummarySensor(coordinator, entry),
        HAFitnessPersonalWeeklyExerciseStatisticsSensor(coordinator, entry),
        HAFitnessPersonalWeeklyMuscleGroupStatisticsSensor(coordinator, entry),
        HAFitnessPersonalWeeklyVolumeHistorySensor(coordinator, entry),
        HAFitnessPersonalWeeklyMetricHistorySensor(coordinator, entry),
        HAFitnessPersonalTrainingBalanceSensor(coordinator, entry),
        HAFitnessHouseholdWeeklySummarySensor(coordinator, entry),
        HAFitnessHouseholdWeeklyMetricHistorySensor(coordinator, entry),
        HAFitnessExerciseCatalogSensor(coordinator, entry),
        HAFitnessExerciseStatisticsSensor(coordinator, entry),
        HAFitnessEquipmentCatalogSensor(coordinator, entry),
        HAFitnessEquipmentStatisticsSensor(coordinator, entry),
        HAFitnessMuscleGroupStatisticsSensor(coordinator, entry),
    ]

    for exercise_id in coordinator.enabled_exercise_ids:
        entities.extend(_build_exercise_metric_entities(coordinator, entry, exercise_id))

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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "workout_active": self._coordinator.is_workout_active,
            "input_enabled": self._coordinator.is_workout_active,
            "selection_required": True,
            "confirmation_action": self._coordinator.pending_confirmation_action,
            "confirmation_expires_at": self._coordinator.pending_confirmation_expires_at,
            "confirmation_seconds_remaining": self._coordinator.confirmation_seconds_remaining,
        }


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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "active_exercise_id": self._coordinator.active_exercise,
            "metric_type": self._coordinator.active_exercise_metric_type,
            "workout_active": self._coordinator.is_workout_active,
        }


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
        if not coord.is_workout_active:
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
            "active_exercise_metric_type": coord.active_exercise_metric_type,
            "active_equipment": coord.active_equipment_display,
            "active_equipment_id": coord.active_equipment,
            "weight": coord.weight,
            "reps": coord.reps,
            "notes": coord.notes,
            "duration_minutes": coord.duration_minutes,
            "distance_km": coord.distance_km,
            "calories": coord.calories,
            "steps": coord.steps,
            "avg_heart_rate": coord.avg_heart_rate,
            "max_heart_rate": coord.max_heart_rate,
            "added_weight": coord.added_weight,
            "intensity": coord.intensity,
            "current_set_number": coord.current_set_number,
            "current_set_volume": coord.weight * coord.reps,
            "last_set_summary": coord.last_set_summary,
            "total_volume": coord.total_volume,
            "total_sets": coord.total_sets,
            "total_workouts": coord.total_workouts,
            "confirmation_action": coord.pending_confirmation_action,
            "confirmation_expires_at": coord.pending_confirmation_expires_at,
            "confirmation_seconds_remaining": coord.confirmation_seconds_remaining,
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


class HAFitnessPersonalRecentWorkoutsSensor(_HAFitnessSensorBase):
    """Sensor exposing recent personal workouts as one aggregate attribute payload."""

    _attr_translation_key = "personal_recent_workouts"

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_personal_recent_workouts"

    @property
    def native_value(self) -> int:
        return len(self._coordinator.get_recent_workouts())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "user_id": self._coordinator.get_recent_workouts_user_id(),
            "limit": self._coordinator.get_recent_workouts_limit(),
            "workouts": self._coordinator.get_recent_workouts(),
        }


class HAFitnessCoreTotalSensor(_HAFitnessSensorBase):
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: HAFitnessCoordinator,
        entry: ConfigEntry,
        *,
        scope: str,
        metric_key: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._scope = scope
        self._metric_key = metric_key
        self._attr_translation_key = f"{scope}_core_total_{metric_key}"
        self._attr_unique_id = f"{entry.entry_id}_{scope}_core_total_{metric_key}"
        unit_map: dict[str, str | None] = {
            "strength_volume": UnitOfMass.KILOGRAMS,
            "activity_load": "load",
            "duration_minutes": UnitOfTime.MINUTES,
            "distance_km": UnitOfLength.KILOMETERS,
            "reps": None,
            "sets": None,
        }
        self._attr_native_unit_of_measurement = unit_map.get(metric_key)

    def _stats(self) -> dict[str, Any]:
        if self._scope == "household":
            return self._coordinator.get_household_core_total_statistics()
        return self._coordinator.get_personal_core_total_statistics()

    @property
    def native_value(self) -> float | int:
        stats = self._stats()
        if self._metric_key == "strength_volume":
            return float(stats.get("total_strength_volume", 0.0))
        if self._metric_key == "activity_load":
            return float(stats.get("total_activity_load", 0.0))
        if self._metric_key == "duration_minutes":
            return float(stats.get("total_duration_seconds", 0)) / 60.0
        if self._metric_key == "distance_km":
            return float(stats.get("total_distance_m", 0.0)) / 1000.0
        if self._metric_key == "reps":
            return int(stats.get("total_reps", 0))
        if self._metric_key == "sets":
            return int(stats.get("total_sets", 0))
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        stats = self._stats()
        attrs: dict[str, Any] = {
            "scope": self._scope,
            "metric": self._metric_key,
            "last_updated_from_logs": stats.get("last_updated_from_logs"),
            "note": stats.get(
                "note",
                "Totals can decrease when workouts or entries are edited/deleted.",
            ),
        }
        if self._scope == "household":
            attrs["included_user_ids"] = stats.get("included_user_ids")
        else:
            attrs["user_id"] = stats.get("user_id")
        return attrs


class HAFitnessPersonalDailyMetricStatisticsSensor(_HAFitnessSensorBase):
    _attr_translation_key = "personal_daily_metric_statistics"
    _attr_native_unit_of_measurement = "load"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_personal_daily_metric_statistics"

    @property
    def native_value(self) -> float:
        payload = self._coordinator.get_personal_daily_metric_statistics()
        days = list(payload.get("days") or [])
        if not days:
            return 0.0
        return float(days[-1].get("total_activity_load_score", 0.0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self._coordinator.get_personal_daily_metric_statistics())


class HAFitnessHouseholdDailyMetricStatisticsSensor(_HAFitnessSensorBase):
    _attr_translation_key = "household_daily_metric_statistics"
    _attr_native_unit_of_measurement = "load"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_household_daily_metric_statistics"

    @property
    def native_value(self) -> float:
        payload = self._coordinator.get_household_daily_metric_statistics()
        days = list(payload.get("days") or [])
        if not days:
            return 0.0
        return float(days[-1].get("total_activity_load_score", 0.0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self._coordinator.get_household_daily_metric_statistics())


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


class HAFitnessPersonalWeeklyVolumeHistorySensor(_HAFitnessSensorBase):
    _attr_translation_key = "personal_weekly_volume_history"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_personal_weekly_volume_history"

    @property
    def native_value(self) -> float:
        payload = self._coordinator.get_personal_weekly_volume_history()
        weeks = list(payload.get("weeks") or [])
        if not weeks:
            return 0.0
        return float(weeks[-1].get("categorized_volume_total", 0.0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self._coordinator.get_personal_weekly_volume_history())


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


class HAFitnessPersonalWeeklyMetricHistorySensor(_HAFitnessSensorBase):
    _attr_translation_key = "personal_weekly_metric_history"
    _attr_native_unit_of_measurement = "load"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_personal_weekly_metric_history"

    @property
    def native_value(self) -> float:
        payload = self._coordinator.get_personal_weekly_metric_history()
        weeks = list(payload.get("weeks") or [])
        if not weeks:
            return 0.0
        return float(weeks[-1].get("total_load_score", 0.0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self._coordinator.get_personal_weekly_metric_history())


class HAFitnessHouseholdWeeklyMetricHistorySensor(_HAFitnessSensorBase):
    _attr_translation_key = "household_weekly_metric_history"
    _attr_native_unit_of_measurement = "load"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HAFitnessCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_household_weekly_metric_history"

    @property
    def native_value(self) -> float:
        payload = self._coordinator.get_household_weekly_metric_history()
        weeks = list(payload.get("weeks") or [])
        if not weeks:
            return 0.0
        return float(weeks[-1].get("total_load_score", 0.0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self._coordinator.get_household_weekly_metric_history())


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


class _ExerciseMetricBaseSensor(SensorEntity):
    """Base class for metric-type-aware exercise sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HAFitnessCoordinator,
        entry: ConfigEntry,
        exercise_id: str,
        *,
        translation_key: str,
        unique_id: str,
        scope: str,
    ) -> None:
        exercise_key = _exercise_key(exercise_id)
        self._coordinator = coordinator
        self._exercise_id = exercise_id
        self._scope = scope
        self._attr_translation_key = translation_key
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id, "exercise", exercise_key)},
            name=coordinator.exercise_display_name(exercise_id),
            manufacturer="HAGym",
            model="HAGym Exercise",
            via_device=(DOMAIN, entry.entry_id),
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
        return self._coordinator.exercise_enabled(self._exercise_id)

    def _stats(self) -> dict[str, Any]:
        return self._coordinator.get_exercise_metric_statistics(
            self._exercise_id, self._scope
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attributes = self._coordinator.get_exercise_muscle_group_attributes(
            self._exercise_id
        )
        attributes["exercise_id"] = self._exercise_id
        attributes["metric_type"] = self._coordinator.exercise_metric_type(
            self._exercise_id
        )
        attributes["scope"] = self._scope
        return attributes


class HAFitnessExerciseMetricNumericSensor(_ExerciseMetricBaseSensor):
    """Numeric exercise sensor mapped to one stats field."""

    def __init__(
        self,
        coordinator: HAFitnessCoordinator,
        entry: ConfigEntry,
        exercise_id: str,
        *,
        translation_key: str,
        unique_id: str,
        scope: str,
        field: str,
        unit: str | None = None,
        state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT,
        multiplier: float = 1.0,
    ) -> None:
        super().__init__(
            coordinator,
            entry,
            exercise_id,
            translation_key=translation_key,
            unique_id=unique_id,
            scope=scope,
        )
        self._field = field
        self._multiplier = float(multiplier)
        if unit is not None:
            self._attr_native_unit_of_measurement = unit
        if state_class is not None:
            self._attr_state_class = state_class

    @property
    def native_value(self) -> float:
        value = self._stats().get(self._field, 0.0)
        try:
            resolved = float(value)
        except (TypeError, ValueError):
            resolved = 0.0
        return resolved * self._multiplier


class HAFitnessExerciseMetricTextSensor(_ExerciseMetricBaseSensor):
    """Text exercise sensor for last entry/set summaries."""

    def __init__(
        self,
        coordinator: HAFitnessCoordinator,
        entry: ConfigEntry,
        exercise_id: str,
        *,
        translation_key: str,
        unique_id: str,
        scope: str,
        field: str,
    ) -> None:
        super().__init__(
            coordinator,
            entry,
            exercise_id,
            translation_key=translation_key,
            unique_id=unique_id,
            scope=scope,
        )
        self._field = field

    @property
    def native_value(self) -> str:
        value = self._stats().get(self._field)
        if value is None:
            return "none"
        text = str(value).strip()
        return text if text else "none"


def _build_exercise_metric_entities(
    coordinator: HAFitnessCoordinator,
    entry: ConfigEntry,
    exercise_id: str,
) -> list[SensorEntity]:
    metric_type = coordinator.exercise_metric_type(exercise_id)
    exercise_key = _exercise_key(exercise_id)
    entities: list[SensorEntity] = []

    if metric_type == METRIC_TYPE_STRENGTH:
        entities.extend(
            [
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_total_volume",
                    unique_id=f"{entry.entry_id}_personal_volume_{exercise_key}_total",
                    scope="personal",
                    field="total_volume",
                    unit=UnitOfMass.KILOGRAMS,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_total_volume",
                    unique_id=f"{entry.entry_id}_household_volume_{exercise_key}_total",
                    scope="household",
                    field="total_volume",
                    unit=UnitOfMass.KILOGRAMS,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_pr",
                    unique_id=f"{entry.entry_id}_personal_pr_{exercise_key}",
                    scope="personal",
                    field="pr_weight",
                    unit=UnitOfMass.KILOGRAMS,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_pr",
                    unique_id=f"{entry.entry_id}_household_pr_{exercise_key}",
                    scope="household",
                    field="pr_weight",
                    unit=UnitOfMass.KILOGRAMS,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_total_sets",
                    unique_id=f"{entry.entry_id}_exercise_personal_total_sets_{exercise_key}",
                    scope="personal",
                    field="total_sets",
                    unit="count",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_total_sets",
                    unique_id=f"{entry.entry_id}_exercise_household_total_sets_{exercise_key}",
                    scope="household",
                    field="total_sets",
                    unit="count",
                ),
                HAFitnessExerciseMetricTextSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_last_set",
                    unique_id=f"{entry.entry_id}_exercise_last_set_{exercise_key}",
                    scope="personal",
                    field="last_entry_summary",
                ),
            ]
        )
        return entities

    if metric_type == METRIC_TYPE_BODYWEIGHT:
        entities.extend(
            [
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_total_reps",
                    unique_id=f"{entry.entry_id}_exercise_personal_total_reps_{exercise_key}",
                    scope="personal",
                    field="total_reps",
                    unit="count",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_total_reps",
                    unique_id=f"{entry.entry_id}_exercise_household_total_reps_{exercise_key}",
                    scope="household",
                    field="total_reps",
                    unit="count",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_best_reps",
                    unique_id=f"{entry.entry_id}_exercise_personal_best_reps_{exercise_key}",
                    scope="personal",
                    field="best_reps",
                    unit="count",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_best_reps",
                    unique_id=f"{entry.entry_id}_exercise_household_best_reps_{exercise_key}",
                    scope="household",
                    field="best_reps",
                    unit="count",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_total_sets",
                    unique_id=f"{entry.entry_id}_exercise_personal_total_sets_{exercise_key}",
                    scope="personal",
                    field="entry_count",
                    unit="count",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_total_sets",
                    unique_id=f"{entry.entry_id}_exercise_household_total_sets_{exercise_key}",
                    scope="household",
                    field="entry_count",
                    unit="count",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_total_load",
                    unique_id=f"{entry.entry_id}_exercise_personal_total_load_{exercise_key}",
                    scope="personal",
                    field="total_load_score",
                    unit="load",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_total_load",
                    unique_id=f"{entry.entry_id}_exercise_household_total_load_{exercise_key}",
                    scope="household",
                    field="total_load_score",
                    unit="load",
                ),
                HAFitnessExerciseMetricTextSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_last_entry",
                    unique_id=f"{entry.entry_id}_exercise_last_entry_{exercise_key}",
                    scope="personal",
                    field="last_entry_summary",
                ),
            ]
        )
        return entities

    if metric_type in (METRIC_TYPE_DURATION, METRIC_TYPE_HOLD):
        entities.extend(
            [
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_total_duration",
                    unique_id=f"{entry.entry_id}_exercise_personal_total_duration_{exercise_key}",
                    scope="personal",
                    field="total_duration_seconds",
                    unit=UnitOfTime.MINUTES,
                    multiplier=1.0 / 60.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_total_duration",
                    unique_id=f"{entry.entry_id}_exercise_household_total_duration_{exercise_key}",
                    scope="household",
                    field="total_duration_seconds",
                    unit=UnitOfTime.MINUTES,
                    multiplier=1.0 / 60.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_best_duration",
                    unique_id=f"{entry.entry_id}_exercise_personal_best_duration_{exercise_key}",
                    scope="personal",
                    field="best_duration_seconds",
                    unit=UnitOfTime.MINUTES,
                    multiplier=1.0 / 60.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_best_duration",
                    unique_id=f"{entry.entry_id}_exercise_household_best_duration_{exercise_key}",
                    scope="household",
                    field="best_duration_seconds",
                    unit=UnitOfTime.MINUTES,
                    multiplier=1.0 / 60.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_entries",
                    unique_id=f"{entry.entry_id}_exercise_personal_entries_{exercise_key}",
                    scope="personal",
                    field="entry_count",
                    unit="count",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_entries",
                    unique_id=f"{entry.entry_id}_exercise_household_entries_{exercise_key}",
                    scope="household",
                    field="entry_count",
                    unit="count",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_total_load",
                    unique_id=f"{entry.entry_id}_exercise_personal_total_load_{exercise_key}",
                    scope="personal",
                    field="total_load_score",
                    unit="load",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_total_load",
                    unique_id=f"{entry.entry_id}_exercise_household_total_load_{exercise_key}",
                    scope="household",
                    field="total_load_score",
                    unit="load",
                ),
                HAFitnessExerciseMetricTextSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_last_entry",
                    unique_id=f"{entry.entry_id}_exercise_last_entry_{exercise_key}",
                    scope="personal",
                    field="last_entry_summary",
                ),
            ]
        )
        return entities

    if metric_type == METRIC_TYPE_DISTANCE:
        entities.extend(
            [
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_total_distance",
                    unique_id=f"{entry.entry_id}_exercise_personal_total_distance_{exercise_key}",
                    scope="personal",
                    field="total_distance_m",
                    unit=UnitOfLength.KILOMETERS,
                    multiplier=1.0 / 1000.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_total_distance",
                    unique_id=f"{entry.entry_id}_exercise_household_total_distance_{exercise_key}",
                    scope="household",
                    field="total_distance_m",
                    unit=UnitOfLength.KILOMETERS,
                    multiplier=1.0 / 1000.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_total_duration",
                    unique_id=f"{entry.entry_id}_exercise_personal_total_duration_{exercise_key}",
                    scope="personal",
                    field="total_duration_seconds",
                    unit=UnitOfTime.MINUTES,
                    multiplier=1.0 / 60.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_total_duration",
                    unique_id=f"{entry.entry_id}_exercise_household_total_duration_{exercise_key}",
                    scope="household",
                    field="total_duration_seconds",
                    unit=UnitOfTime.MINUTES,
                    multiplier=1.0 / 60.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_best_distance",
                    unique_id=f"{entry.entry_id}_exercise_personal_best_distance_{exercise_key}",
                    scope="personal",
                    field="best_distance_m",
                    unit=UnitOfLength.KILOMETERS,
                    multiplier=1.0 / 1000.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_best_distance",
                    unique_id=f"{entry.entry_id}_exercise_household_best_distance_{exercise_key}",
                    scope="household",
                    field="best_distance_m",
                    unit=UnitOfLength.KILOMETERS,
                    multiplier=1.0 / 1000.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_best_pace",
                    unique_id=f"{entry.entry_id}_exercise_personal_best_pace_{exercise_key}",
                    scope="personal",
                    field="best_pace_seconds_per_km",
                    unit="min/km",
                    multiplier=1.0 / 60.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_best_pace",
                    unique_id=f"{entry.entry_id}_exercise_household_best_pace_{exercise_key}",
                    scope="household",
                    field="best_pace_seconds_per_km",
                    unit="min/km",
                    multiplier=1.0 / 60.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_total_load",
                    unique_id=f"{entry.entry_id}_exercise_personal_total_load_{exercise_key}",
                    scope="personal",
                    field="total_load_score",
                    unit="load",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_total_load",
                    unique_id=f"{entry.entry_id}_exercise_household_total_load_{exercise_key}",
                    scope="household",
                    field="total_load_score",
                    unit="load",
                ),
                HAFitnessExerciseMetricTextSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_last_entry",
                    unique_id=f"{entry.entry_id}_exercise_last_entry_{exercise_key}",
                    scope="personal",
                    field="last_entry_summary",
                ),
            ]
        )
        return entities

    if metric_type == METRIC_TYPE_CARDIO:
        entities.extend(
            [
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_total_duration",
                    unique_id=f"{entry.entry_id}_exercise_personal_total_duration_{exercise_key}",
                    scope="personal",
                    field="total_duration_seconds",
                    unit=UnitOfTime.MINUTES,
                    multiplier=1.0 / 60.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_total_duration",
                    unique_id=f"{entry.entry_id}_exercise_household_total_duration_{exercise_key}",
                    scope="household",
                    field="total_duration_seconds",
                    unit=UnitOfTime.MINUTES,
                    multiplier=1.0 / 60.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_total_distance",
                    unique_id=f"{entry.entry_id}_exercise_personal_total_distance_{exercise_key}",
                    scope="personal",
                    field="total_distance_m",
                    unit=UnitOfLength.KILOMETERS,
                    multiplier=1.0 / 1000.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_total_distance",
                    unique_id=f"{entry.entry_id}_exercise_household_total_distance_{exercise_key}",
                    scope="household",
                    field="total_distance_m",
                    unit=UnitOfLength.KILOMETERS,
                    multiplier=1.0 / 1000.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_total_calories",
                    unique_id=f"{entry.entry_id}_exercise_personal_total_calories_{exercise_key}",
                    scope="personal",
                    field="total_calories",
                    unit="kcal",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_total_calories",
                    unique_id=f"{entry.entry_id}_exercise_household_total_calories_{exercise_key}",
                    scope="household",
                    field="total_calories",
                    unit="kcal",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_total_steps",
                    unique_id=f"{entry.entry_id}_exercise_personal_total_steps_{exercise_key}",
                    scope="personal",
                    field="total_steps",
                    unit="count",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_total_steps",
                    unique_id=f"{entry.entry_id}_exercise_household_total_steps_{exercise_key}",
                    scope="household",
                    field="total_steps",
                    unit="count",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_avg_heart_rate",
                    unique_id=f"{entry.entry_id}_exercise_personal_avg_heart_rate_{exercise_key}",
                    scope="personal",
                    field="avg_heart_rate",
                    unit="bpm",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_max_heart_rate",
                    unique_id=f"{entry.entry_id}_exercise_personal_max_heart_rate_{exercise_key}",
                    scope="personal",
                    field="max_heart_rate",
                    unit="bpm",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_max_heart_rate",
                    unique_id=f"{entry.entry_id}_exercise_household_max_heart_rate_{exercise_key}",
                    scope="household",
                    field="max_heart_rate",
                    unit="bpm",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_total_load",
                    unique_id=f"{entry.entry_id}_exercise_personal_total_load_{exercise_key}",
                    scope="personal",
                    field="total_load_score",
                    unit="load",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_total_load",
                    unique_id=f"{entry.entry_id}_exercise_household_total_load_{exercise_key}",
                    scope="household",
                    field="total_load_score",
                    unit="load",
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_best_duration",
                    unique_id=f"{entry.entry_id}_exercise_personal_best_duration_{exercise_key}",
                    scope="personal",
                    field="best_duration_seconds",
                    unit=UnitOfTime.MINUTES,
                    multiplier=1.0 / 60.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_best_distance",
                    unique_id=f"{entry.entry_id}_exercise_personal_best_distance_{exercise_key}",
                    scope="personal",
                    field="best_distance_m",
                    unit=UnitOfLength.KILOMETERS,
                    multiplier=1.0 / 1000.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_personal_best_pace",
                    unique_id=f"{entry.entry_id}_exercise_personal_best_pace_{exercise_key}",
                    scope="personal",
                    field="best_pace_seconds_per_km",
                    unit="min/km",
                    multiplier=1.0 / 60.0,
                ),
                HAFitnessExerciseMetricNumericSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_household_best_pace",
                    unique_id=f"{entry.entry_id}_exercise_household_best_pace_{exercise_key}",
                    scope="household",
                    field="best_pace_seconds_per_km",
                    unit="min/km",
                    multiplier=1.0 / 60.0,
                ),
                HAFitnessExerciseMetricTextSensor(
                    coordinator,
                    entry,
                    exercise_id,
                    translation_key="exercise_last_entry",
                    unique_id=f"{entry.entry_id}_exercise_last_entry_{exercise_key}",
                    scope="personal",
                    field="last_entry_summary",
                ),
            ]
        )
        return entities

    # Custom / fallback metrics
    entities.extend(
        [
            HAFitnessExerciseMetricNumericSensor(
                coordinator,
                entry,
                exercise_id,
                translation_key="exercise_personal_entries",
                unique_id=f"{entry.entry_id}_exercise_personal_entries_{exercise_key}",
                scope="personal",
                field="entry_count",
                unit="count",
            ),
            HAFitnessExerciseMetricNumericSensor(
                coordinator,
                entry,
                exercise_id,
                translation_key="exercise_household_entries",
                unique_id=f"{entry.entry_id}_exercise_household_entries_{exercise_key}",
                scope="household",
                field="entry_count",
                unit="count",
            ),
            HAFitnessExerciseMetricNumericSensor(
                coordinator,
                entry,
                exercise_id,
                translation_key="exercise_personal_total_load",
                unique_id=f"{entry.entry_id}_exercise_personal_total_load_{exercise_key}",
                scope="personal",
                field="total_load_score",
                unit="load",
            ),
            HAFitnessExerciseMetricNumericSensor(
                coordinator,
                entry,
                exercise_id,
                translation_key="exercise_household_total_load",
                unique_id=f"{entry.entry_id}_exercise_household_total_load_{exercise_key}",
                scope="household",
                field="total_load_score",
                unit="load",
            ),
            HAFitnessExerciseMetricNumericSensor(
                coordinator,
                entry,
                exercise_id,
                translation_key="exercise_personal_total_duration",
                unique_id=f"{entry.entry_id}_exercise_personal_total_duration_{exercise_key}",
                scope="personal",
                field="total_duration_seconds",
                unit=UnitOfTime.MINUTES,
                multiplier=1.0 / 60.0,
            ),
            HAFitnessExerciseMetricNumericSensor(
                coordinator,
                entry,
                exercise_id,
                translation_key="exercise_household_total_duration",
                unique_id=f"{entry.entry_id}_exercise_household_total_duration_{exercise_key}",
                scope="household",
                field="total_duration_seconds",
                unit=UnitOfTime.MINUTES,
                multiplier=1.0 / 60.0,
            ),
            HAFitnessExerciseMetricNumericSensor(
                coordinator,
                entry,
                exercise_id,
                translation_key="exercise_personal_total_distance",
                unique_id=f"{entry.entry_id}_exercise_personal_total_distance_{exercise_key}",
                scope="personal",
                field="total_distance_m",
                unit=UnitOfLength.KILOMETERS,
                multiplier=1.0 / 1000.0,
            ),
            HAFitnessExerciseMetricNumericSensor(
                coordinator,
                entry,
                exercise_id,
                translation_key="exercise_household_total_distance",
                unique_id=f"{entry.entry_id}_exercise_household_total_distance_{exercise_key}",
                scope="household",
                field="total_distance_m",
                unit=UnitOfLength.KILOMETERS,
                multiplier=1.0 / 1000.0,
            ),
            HAFitnessExerciseMetricTextSensor(
                coordinator,
                entry,
                exercise_id,
                translation_key="exercise_last_entry",
                unique_id=f"{entry.entry_id}_exercise_last_entry_{exercise_key}",
                scope="personal",
                field="last_entry_summary",
            ),
        ]
    )
    return entities


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
        "metric_type": row.get("metric_type"),
        "enabled": int(row.get("enabled", 1)) == 1,
        "sort_order": int(row.get("sort_order", 0)),
        "created_at": row.get("created_at"),
    }


def _equipment_row_payload(row: dict[str, Any]) -> dict[str, Any]:
    equipment_id = str(row.get("id") or "")
    return {
        "id": equipment_id,
        "name": row.get("name"),
        "name_en": row.get("name_en"),
        "name_de": row.get("name_de"),
        "description": row.get("description"),
        "icon": row.get("icon"),
        "location": row.get("location"),
        "enabled": int(row.get("enabled", 1)) == 1,
        "sort_order": int(row.get("sort_order", 100)),
        "created_at": row.get("created_at"),
    }
