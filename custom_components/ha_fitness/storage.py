"""SQLite storage layer for HAGym."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import sqlite3
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant

from .const import (
    DEFAULT_METRIC_TYPE,
    DEFAULT_EQUIPMENT,
    DEFAULT_EXERCISE_MUSCLE_GROUP_MAP,
    DEFAULT_EXERCISE_EQUIPMENT_MAP,
    DEFAULT_EXERCISES,
    DEFAULT_MUSCLE_GROUPS,
    DEFAULT_MUSCLE_ROLE_WEIGHT_FACTORS,
    METRIC_TYPE_BODYWEIGHT,
    METRIC_TYPE_CARDIO,
    METRIC_TYPE_CUSTOM,
    METRIC_TYPE_DISTANCE,
    METRIC_TYPE_DURATION,
    METRIC_TYPE_HOLD,
    METRIC_TYPE_STRENGTH,
    MUSCLE_ROLE_PRIMARY,
    MUSCLE_ROLE_SECONDARY,
    MUSCLE_ROLE_STABILIZER,
    LEGACY_USER_ID,
    SUPPORTED_METRIC_TYPES,
)
from .migrations import apply_migrations

_LOGGER = logging.getLogger(__name__)
_WEEKLY_HISTORY_PUSH_IDS = {"chest", "shoulders", "triceps"}
_WEEKLY_HISTORY_PULL_IDS = {
    "back",
    "lats",
    "rhomboids",
    "traps",
    "biceps",
    "forearms",
    "erector_spinae",
}
_WEEKLY_HISTORY_LEGS_IDS = {
    "quadriceps",
    "hamstrings",
    "glutes",
    "calves",
    "adductors",
    "abductors",
}
_WEEKLY_HISTORY_CORE_IDS = {"core", "abs", "obliques"}

# Tolerance for normalized muscle-group weight sums (1.0 ± tolerance)
_MUSCLE_WEIGHT_TOLERANCE = 0.001


class HAFitnessStore:
    """SQLite-backed persistence helper for HAGym."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._db_path = hass.config.path("ha_fitness", "ha_fitness.db")

    async def async_initialize(self) -> None:
        """Initialize database directory, file, and schema."""
        await self._hass.async_add_executor_job(self._initialize)

    async def async_start_workout(self, user_id: str, started_at: datetime) -> int:
        """Create a workout row and return its id."""
        return await self._hass.async_add_executor_job(self._start_workout, user_id, started_at)

    async def async_finish_workout(self, workout_id: int, finished_at: datetime) -> None:
        """Mark a workout as finished."""
        await self._hass.async_add_executor_job(self._finish_workout, workout_id, finished_at)

    async def async_save_set(
        self,
        user_id: str,
        workout_id: int | None,
        exercise: str,
        exercise_id: str | None,
        equipment_id: str | None,
        weight: float,
        reps: int,
        volume: float,
        notes: str | None,
        created_at: datetime,
        metric_type: str | None = None,
        duration_seconds: int | None = None,
        distance_m: float | None = None,
        calories: float | None = None,
        steps: int | None = None,
        avg_heart_rate: float | None = None,
        max_heart_rate: float | None = None,
        avg_power_watts: float | None = None,
        max_power_watts: float | None = None,
        avg_speed_mps: float | None = None,
        load_score: float | None = None,
        intensity: str | None = None,
        source: str | None = None,
        added_weight: float | None = None,
    ) -> int:
        """Persist a set row and return its id."""
        return await self._hass.async_add_executor_job(
            self._save_set,
            user_id,
            workout_id,
            exercise,
            exercise_id,
            equipment_id,
            weight,
            reps,
            volume,
            notes,
            created_at,
            metric_type,
            duration_seconds,
            distance_m,
            calories,
            steps,
            avg_heart_rate,
            max_heart_rate,
            avg_power_watts,
            max_power_watts,
            avg_speed_mps,
            load_score,
            intensity,
            source,
            added_weight,
        )

    async def async_get_last_set(self) -> dict[str, Any] | None:
        """Return most recent set."""
        return await self._hass.async_add_executor_job(self._get_last_set)

    async def async_get_last_set_for_exercise(self, exercise_id: str) -> dict[str, Any] | None:
        """Return most recent set for one exercise."""
        return await self._hass.async_add_executor_job(self._get_last_set_for_exercise, exercise_id)

    async def async_get_current_open_workout(self, user_id: str) -> dict[str, Any] | None:
        """Return open workout where finished_at is NULL for one user."""
        return await self._hass.async_add_executor_job(self._get_current_open_workout, user_id)

    async def async_get_workouts(
        self, user_id: str | None = None, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Return workout history rows sorted by started_at desc."""
        return await self._hass.async_add_executor_job(
            self._get_workouts,
            user_id,
            limit,
            offset,
        )

    async def async_get_workout(self, workout_id: int) -> dict[str, Any] | None:
        """Return one workout by id."""
        return await self._hass.async_add_executor_job(self._get_workout, workout_id)

    async def async_create_workout(
        self,
        user_id: str,
        started_at: datetime,
        ended_at: datetime | None = None,
        notes: str | None = None,
        status: str = "completed",
    ) -> dict[str, Any]:
        """Create one workout and return the stored row."""
        return await self._hass.async_add_executor_job(
            self._create_workout, user_id, started_at, ended_at, notes, status
        )

    async def async_update_workout(
        self,
        workout_id: int,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        notes: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Update one workout and return the updated row."""
        return await self._hass.async_add_executor_job(
            self._update_workout, workout_id, started_at, ended_at, notes, status
        )

    async def async_delete_workout(self, workout_id: int, delete_sets: bool = True) -> None:
        """Delete one workout, optionally deleting related sets."""
        await self._hass.async_add_executor_job(
            self._delete_workout, workout_id, delete_sets
        )

    async def async_get_sets_for_workout(self, workout_id: int) -> list[dict[str, Any]]:
        """Return sets for one workout ordered by created_at asc."""
        return await self._hass.async_add_executor_job(
            self._get_sets_for_workout, workout_id
        )

    async def async_add_set_to_workout(
        self,
        workout_id: int,
        user_id: str,
        equipment_id: str | None,
        exercise_id: str,
        weight: float,
        reps: int,
        notes: str | None = None,
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Insert a set tied to one workout and return the inserted row."""
        return await self._hass.async_add_executor_job(
            self._add_set_to_workout,
            workout_id,
            user_id,
            equipment_id,
            exercise_id,
            weight,
            reps,
            notes,
            created_at,
        )

    async def async_update_set(
        self,
        set_id: int,
        equipment_id: str | None = None,
        exercise_id: str | None = None,
        weight: float | None = None,
        reps: int | None = None,
        notes: str | None = None,
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Update one set and return the updated row."""
        return await self._hass.async_add_executor_job(
            self._update_set,
            set_id,
            equipment_id,
            exercise_id,
            weight,
            reps,
            notes,
            created_at,
        )

    async def async_delete_set(self, set_id: int) -> None:
        """Delete one set row by id."""
        await self._hass.async_add_executor_job(self._delete_set, set_id)

    async def async_get_total_volume(self, user_id: str | None = None) -> float:
        """Return total volume, optionally filtered by user."""
        return await self._hass.async_add_executor_job(self._get_total_volume, user_id)

    async def async_get_total_volume_by_exercise(
        self, exercise_id: str, user_id: str | None = None
    ) -> float:
        """Return total volume for an exercise, optionally filtered by user."""
        return await self._hass.async_add_executor_job(
            self._get_total_volume_by_exercise, exercise_id, user_id
        )

    async def async_get_pr_by_exercise(self, exercise_id: str, user_id: str | None = None) -> float:
        """Return max weight for an exercise, optionally filtered by user."""
        return await self._hass.async_add_executor_job(self._get_pr_by_exercise, exercise_id, user_id)

    async def async_get_set_count(self, user_id: str | None = None) -> int:
        """Return set count, optionally filtered by user."""
        return await self._hass.async_add_executor_job(self._get_set_count, user_id)

    async def async_get_set_count_for_workout(self, workout_id: int) -> int:
        """Return set count for one workout."""
        return await self._hass.async_add_executor_job(
            self._get_set_count_for_workout, workout_id
        )

    async def async_get_workout_count(self, user_id: str | None = None) -> int:
        """Return workout count, optionally filtered by user."""
        return await self._hass.async_add_executor_job(self._get_workout_count, user_id)

    async def async_get_recent_sets(
        self, limit: int = 10, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return most recent set rows, optionally filtered by user."""
        return await self._hass.async_add_executor_job(self._get_recent_sets, limit, user_id)

    async def async_upsert_user(self, user_id: str, display_name: str | None = None) -> None:
        """Insert or update one user row."""
        await self._hass.async_add_executor_job(self._upsert_user, user_id, display_name)

    async def async_get_users(self) -> list[dict[str, Any]]:
        """Return known users sorted by display_name/id."""
        return await self._hass.async_add_executor_job(self._get_users)

    async def async_get_user(self, user_id: str) -> dict[str, Any] | None:
        """Return one user row by id."""
        return await self._hass.async_add_executor_job(self._get_user, user_id)

    async def async_get_exercises(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        """Return exercise catalog rows."""
        return await self._hass.async_add_executor_job(self._get_exercises, enabled_only)

    async def async_get_exercise(self, exercise_id: str) -> dict[str, Any] | None:
        """Return one exercise by id."""
        return await self._hass.async_add_executor_job(self._get_exercise, exercise_id)

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
        uses_bodyweight: bool = False,
        bodyweight_factor: float = 1.0,
    ) -> None:
        """Insert one exercise row or reactivate/update if it already exists."""
        await self._hass.async_add_executor_job(
            self._add_exercise,
            exercise_id,
            name_en,
            name_de,
            muscle_group,
            equipment,
            equipment_id,
            metric_type,
            enabled,
            sort_order,
            uses_bodyweight,
            bodyweight_factor,
        )

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
        uses_bodyweight: bool | None = None,
        bodyweight_factor: float | None = None,
    ) -> bool:
        """Update one exercise row and return whether a row was modified."""
        return await self._hass.async_add_executor_job(
            self._update_exercise,
            exercise_id,
            name_en,
            name_de,
            muscle_group,
            equipment,
            equipment_id,
            metric_type,
            enabled,
            sort_order,
            uses_bodyweight,
            bodyweight_factor,
        )

    async def async_get_exercise_metric_type(self, exercise_id: str) -> str:
        """Return metric type for one exercise id."""
        return await self._hass.async_add_executor_job(
            self._get_exercise_metric_type, exercise_id
        )

    async def async_get_set_log(self, set_id: int) -> dict[str, Any] | None:
        """Return one set_log row by id."""
        return await self._hass.async_add_executor_job(self._get_set_log, set_id)

    async def async_save_activity_entry(
        self,
        *,
        user_id: str,
        workout_id: int | None,
        exercise_id: str,
        metric_type: str,
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
        equipment_id: str | None = None,
        added_weight: float | None = None,
    ) -> int:
        """Persist one non-strength training entry and return its id."""
        return await self._hass.async_add_executor_job(
            self._save_activity_entry,
            user_id,
            workout_id,
            exercise_id,
            metric_type,
            reps,
            duration_seconds,
            distance_m,
            calories,
            steps,
            avg_heart_rate,
            max_heart_rate,
            avg_power_watts,
            max_power_watts,
            avg_speed_mps,
            intensity,
            source,
            notes,
            created_at,
            equipment_id,
            added_weight,
        )

    async def async_disable_exercise(self, exercise_id: str) -> bool:
        """Disable one exercise by id."""
        return await self._hass.async_add_executor_job(self._disable_exercise, exercise_id)

    async def async_refresh_exercises(self) -> None:
        """Re-seed built-in catalog entries."""
        await self._hass.async_add_executor_job(self._refresh_exercises)

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
        """Insert equipment row or update if it already exists."""
        await self._hass.async_add_executor_job(
            self._add_equipment,
            equipment_id,
            name,
            name_en,
            name_de,
            description,
            icon,
            location,
            enabled,
            sort_order,
        )

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
        """Update equipment row and return whether a row was modified."""
        return await self._hass.async_add_executor_job(
            self._update_equipment,
            equipment_id,
            name,
            name_en,
            name_de,
            description,
            icon,
            location,
            enabled,
            sort_order,
        )

    async def async_disable_equipment(self, equipment_id: str) -> bool:
        """Disable one equipment by id."""
        return await self._hass.async_add_executor_job(self._disable_equipment, equipment_id)

    async def async_get_equipment(self, equipment_id: str) -> dict[str, Any] | None:
        """Return one equipment by id."""
        return await self._hass.async_add_executor_job(self._get_equipment, equipment_id)

    async def async_get_all_equipment(self) -> list[dict[str, Any]]:
        """Return all equipment rows."""
        return await self._hass.async_add_executor_job(self._get_all_equipment)

    async def async_get_enabled_equipment(self) -> list[dict[str, Any]]:
        """Return enabled equipment rows."""
        return await self._hass.async_add_executor_job(self._get_enabled_equipment)

    async def async_assign_exercise_to_equipment(
        self, exercise_id: str, equipment_id: str | None
    ) -> bool:
        """Assign one exercise to equipment."""
        return await self._hass.async_add_executor_job(
            self._assign_exercise_to_equipment, exercise_id, equipment_id
        )

    async def async_get_exercises_for_equipment(
        self, equipment_id: str | None, enabled_only: bool = True
    ) -> list[dict[str, Any]]:
        """Return exercises mapped to equipment (or all when equipment_id is None)."""
        return await self._hass.async_add_executor_job(
            self._get_exercises_for_equipment, equipment_id, enabled_only
        )

    async def async_get_exercise_statistics(
        self, user_id: str | None = None, household_user_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Return grouped exercise stats for global/personal/household scopes."""
        return await self._hass.async_add_executor_job(
            self._get_exercise_statistics, user_id, household_user_ids
        )

    async def async_get_exercise_metric_statistics(
        self,
        exercise_id: str,
        metric_type: str,
        user_id: str | None = None,
        user_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return metric-type-aware statistics for one exercise and one scope."""
        return await self._hass.async_add_executor_job(
            self._get_exercise_metric_statistics,
            exercise_id,
            metric_type,
            user_id,
            user_ids,
        )

    async def async_get_muscle_groups(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        """Return muscle group catalog rows."""
        return await self._hass.async_add_executor_job(self._get_muscle_groups, enabled_only)

    async def async_get_muscle_group(self, muscle_group_id: str) -> dict[str, Any] | None:
        """Return one muscle group row by id."""
        return await self._hass.async_add_executor_job(self._get_muscle_group, muscle_group_id)

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
        """Insert one muscle group row or reactivate/update if it exists."""
        await self._hass.async_add_executor_job(
            self._add_muscle_group,
            muscle_group_id,
            name_en,
            name_de,
            description,
            icon,
            body_region,
            enabled,
            sort_order,
        )

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
        """Update one muscle group row and return whether modified."""
        return await self._hass.async_add_executor_job(
            self._update_muscle_group,
            muscle_group_id,
            name_en,
            name_de,
            description,
            icon,
            body_region,
            enabled,
            sort_order,
        )

    async def async_disable_muscle_group(self, muscle_group_id: str) -> bool:
        """Disable one muscle group by id."""
        return await self._hass.async_add_executor_job(
            self._disable_muscle_group, muscle_group_id
        )

    async def async_assign_muscle_group_to_exercise(
        self,
        exercise_id: str,
        muscle_group_id: str,
        role: str = MUSCLE_ROLE_PRIMARY,
        weight_factor: float = 1.0,
    ) -> None:
        """Create or update one exercise-to-muscle-group mapping."""
        await self._hass.async_add_executor_job(
            self._assign_muscle_group_to_exercise,
            exercise_id,
            muscle_group_id,
            role,
            weight_factor,
        )

    async def async_remove_muscle_group_from_exercise(
        self, exercise_id: str, muscle_group_id: str
    ) -> bool:
        """Delete one exercise-to-muscle-group mapping."""
        return await self._hass.async_add_executor_job(
            self._remove_muscle_group_from_exercise, exercise_id, muscle_group_id
        )

    async def async_replace_muscle_groups_for_exercise(
        self,
        exercise_id: str,
        primary_ids: list[str],
        secondary_ids: list[str],
        stabilizer_ids: list[str],
    ) -> None:
        """Replace all muscle mappings for one exercise from role buckets.

        Backward-compatible wrapper that auto-normalizes weight factors so they sum to 1.0.
        """
        await self._hass.async_add_executor_job(
            self._replace_muscle_groups_for_exercise,
            exercise_id,
            primary_ids,
            secondary_ids,
            stabilizer_ids,
        )

    async def async_replace_muscle_groups_with_weights(
        self,
        exercise_id: str,
        mappings: list[dict[str, Any]],
    ) -> None:
        """Replace all muscle-group mappings for one exercise with explicit weight factors.

        Each mapping dict must contain at least:
            - 'muscle_group_id' (str)
            - 'role' ('primary', 'secondary', or 'stabilizer')
            - 'weight_factor' (float 0.0-1.0, will be normalized so sum == 1.0)

        Raises ValueError on validation failure.
        """
        await self._hass.async_add_executor_job(
            self._replace_muscle_groups_with_weights,
            exercise_id,
            mappings,
        )

    async def async_get_muscle_groups_for_exercise(self, exercise_id: str) -> list[dict[str, Any]]:
        """Return mapped muscle groups for one exercise."""
        return await self._hass.async_add_executor_job(
            self._get_muscle_groups_for_exercise, exercise_id
        )

    async def async_get_exercises_for_muscle_group(
        self, muscle_group_id: str
    ) -> list[dict[str, Any]]:
        """Return exercises mapped to one muscle group."""
        return await self._hass.async_add_executor_job(
            self._get_exercises_for_muscle_group, muscle_group_id
        )

    async def async_get_muscle_group_statistics(
        self, user_id: str | None = None, household_user_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Return grouped muscle-group stats for global/personal/household scopes."""
        return await self._hass.async_add_executor_job(
            self._get_muscle_group_statistics, user_id, household_user_ids
        )

    async def async_get_equipment_statistics(self) -> list[dict[str, Any]]:
        """Return grouped equipment stats for all users."""
        return await self._hass.async_add_executor_job(self._get_equipment_statistics, None)

    async def async_get_user_equipment_statistics(self, user_id: str) -> list[dict[str, Any]]:
        """Return grouped equipment stats for one user."""
        return await self._hass.async_add_executor_job(self._get_equipment_statistics, [user_id])

    async def async_get_household_equipment_statistics(
        self, user_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Return grouped equipment stats for a household selection."""
        return await self._hass.async_add_executor_job(
            self._get_household_equipment_statistics, user_ids
        )

    async def async_get_household_total_volume(self, user_ids: list[str] | None = None) -> float:
        """Return household total volume."""
        return await self._hass.async_add_executor_job(self._get_household_total_volume, user_ids)

    async def async_get_household_set_count(self, user_ids: list[str] | None = None) -> int:
        """Return household set count."""
        return await self._hass.async_add_executor_job(self._get_household_set_count, user_ids)

    async def async_get_household_workout_count(self, user_ids: list[str] | None = None) -> int:
        """Return household workout count."""
        return await self._hass.async_add_executor_job(
            self._get_household_workout_count, user_ids
        )

    async def async_get_household_recent_sets(
        self, limit: int = 10, user_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Return household recent sets."""
        return await self._hass.async_add_executor_job(
            self._get_household_recent_sets, limit, user_ids
        )

    async def async_get_household_total_volume_by_exercise(
        self, exercise_id: str, user_ids: list[str] | None = None
    ) -> float:
        """Return household exercise volume."""
        return await self._hass.async_add_executor_job(
            self._get_household_total_volume_by_exercise, exercise_id, user_ids
        )

    async def async_get_household_pr_by_exercise(
        self, exercise_id: str, user_ids: list[str] | None = None
    ) -> float:
        """Return household exercise PR."""
        return await self._hass.async_add_executor_job(
            self._get_household_pr_by_exercise, exercise_id, user_ids
        )

    async def async_get_weekly_summary(
        self,
        start_utc: str,
        end_utc: str,
        user_id: str | None = None,
        user_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return aggregate weekly summary for one scope."""
        return await self._hass.async_add_executor_job(
            self._get_weekly_summary,
            start_utc,
            end_utc,
            user_id,
            user_ids,
        )

    async def async_get_weekly_exercise_statistics(
        self,
        start_utc: str,
        end_utc: str,
        user_id: str | None = None,
        user_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return weekly exercise statistics for one scope."""
        return await self._hass.async_add_executor_job(
            self._get_weekly_exercise_statistics,
            start_utc,
            end_utc,
            user_id,
            user_ids,
        )

    async def async_get_weekly_muscle_group_statistics(
        self,
        start_utc: str,
        end_utc: str,
        user_id: str | None = None,
        user_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return weekly weighted muscle-group statistics for one scope."""
        return await self._hass.async_add_executor_job(
            self._get_weekly_muscle_group_statistics,
            start_utc,
            end_utc,
            user_id,
            user_ids,
        )

    async def async_get_weekly_user_statistics(
        self, start_utc: str, end_utc: str, user_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Return weekly per-user statistics for a household/global scope."""
        return await self._hass.async_add_executor_job(
            self._get_weekly_user_statistics,
            start_utc,
            end_utc,
            user_ids,
        )

    async def async_get_weekly_volume_history(
        self,
        week_ranges: list[dict[str, Any]],
        user_id: str | None = None,
        user_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return per-week personal/household/global volume history rows."""
        return await self._hass.async_add_executor_job(
            self._get_weekly_volume_history,
            week_ranges,
            user_id,
            user_ids,
        )

    async def async_get_weekly_metric_history(
        self,
        week_ranges: list[dict[str, Any]],
        user_id: str | None = None,
        user_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return per-week metric-aware history rows for one scope."""
        return await self._hass.async_add_executor_job(
            self._get_weekly_metric_history,
            week_ranges,
            user_id,
            user_ids,
        )

    async def async_get_core_total_statistics(
        self,
        user_id: str | None = None,
        user_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return core total counters for one scope."""
        return await self._hass.async_add_executor_job(
            self._get_core_total_statistics,
            user_id,
            user_ids,
        )

    async def async_get_daily_metric_statistics(
        self,
        day_ranges: list[dict[str, Any]],
        user_id: str | None = None,
        user_ids: list[str] | None = None,
        include_scope_breakdowns: bool = True,
        breakdown_limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return compact per-day metric statistics for one scope."""
        return await self._hass.async_add_executor_job(
            self._get_daily_metric_statistics,
            day_ranges,
            user_id,
            user_ids,
            include_scope_breakdowns,
            breakdown_limit,
        )

    # ------------------------------------------------------------------
    # Sync implementation (executor only)
    # ------------------------------------------------------------------

    def _initialize(self) -> None:
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with self._connect() as conn:
            apply_migrations(conn)
            conn.commit()

    def _start_workout(self, user_id: str, started_at: datetime) -> int:
        iso_started_at = _isoformat(started_at)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO workouts(
                    user_id, started_at, finished_at, ended_at, status, notes, created_at, updated_at
                )
                VALUES(?, ?, NULL, NULL, 'active', NULL, ?, ?)
                """,
                (user_id, iso_started_at, iso_started_at, iso_started_at),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def _finish_workout(self, workout_id: int, finished_at: datetime) -> None:
        ended_at = _isoformat(finished_at)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE workouts
                SET finished_at = ?,
                    ended_at = ?,
                    status = 'completed',
                    updated_at = ?
                WHERE id = ?
                """,
                (ended_at, ended_at, ended_at, workout_id),
            )
            conn.commit()

    def _save_set(
        self,
        user_id: str,
        workout_id: int | None,
        exercise: str,
        exercise_id: str | None,
        equipment_id: str | None,
        weight: float,
        reps: int,
        volume: float,
        notes: str | None,
        created_at: datetime,
        metric_type: str | None = None,
        duration_seconds: int | None = None,
        distance_m: float | None = None,
        calories: float | None = None,
        steps: int | None = None,
        avg_heart_rate: float | None = None,
        max_heart_rate: float | None = None,
        avg_power_watts: float | None = None,
        max_power_watts: float | None = None,
        avg_speed_mps: float | None = None,
        load_score: float | None = None,
        intensity: str | None = None,
        source: str | None = None,
        added_weight: float | None = None,
    ) -> int:
        resolved_metric_type = _normalize_metric_type(metric_type)
        with self._connect() as conn:
            resolved_equipment_id = equipment_id
            if (resolved_equipment_id is None or str(resolved_equipment_id).strip() == "") and exercise_id:
                resolved_equipment_id = self._resolve_equipment_for_exercise(conn, exercise_id)
            cursor = conn.execute(
                """
                INSERT INTO set_logs(
                    user_id, workout_id, exercise, exercise_id, equipment_id, metric_type,
                    weight, reps, volume, notes, created_at, updated_at,
                    duration_seconds, distance_m, calories, steps, avg_heart_rate, max_heart_rate,
                    avg_power_watts, max_power_watts, avg_speed_mps, load_score, intensity, source, added_weight
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    workout_id,
                    exercise,
                    exercise_id,
                    resolved_equipment_id,
                    resolved_metric_type,
                    weight,
                    reps,
                    volume,
                    notes,
                    _isoformat(created_at),
                    _isoformat(created_at),
                    duration_seconds,
                    distance_m,
                    calories,
                    steps,
                    avg_heart_rate,
                    max_heart_rate,
                    avg_power_watts,
                    max_power_watts,
                    avg_speed_mps,
                    load_score,
                    intensity,
                    source,
                    added_weight,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def _get_last_set(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id, user_id, workout_id, exercise, exercise_id, equipment_id, metric_type,
                    weight, reps, volume, notes, created_at, updated_at,
                    duration_seconds, distance_m, calories, steps, avg_heart_rate, max_heart_rate,
                    avg_power_watts, max_power_watts, avg_speed_mps, load_score, intensity, source, added_weight
                FROM set_logs
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            return _row_to_dict(row)

    def _get_last_set_for_exercise(self, exercise_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            where_sql, where_params = self._exercise_predicate(conn, exercise_id)
            row = conn.execute(
                f"""
                SELECT
                    id, user_id, workout_id, exercise, exercise_id, equipment_id, metric_type,
                    weight, reps, volume, notes, created_at, updated_at,
                    duration_seconds, distance_m, calories, steps, avg_heart_rate, max_heart_rate,
                    avg_power_watts, max_power_watts, avg_speed_mps, load_score, intensity, source, added_weight
                FROM set_logs
                WHERE {where_sql}
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                where_params,
            ).fetchone()
            return _row_to_dict(row)

    def _get_current_open_workout(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    user_id,
                    started_at,
                    COALESCE(ended_at, finished_at) AS ended_at,
                    finished_at,
                    COALESCE(status, CASE WHEN COALESCE(ended_at, finished_at) IS NULL THEN 'active' ELSE 'completed' END) AS status,
                    notes,
                    created_at,
                    updated_at
                FROM workouts
                WHERE COALESCE(ended_at, finished_at) IS NULL
                  AND user_id = ?
                ORDER BY started_at DESC, id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            return _row_to_dict(row)

    def _save_activity_entry(
        self,
        user_id: str,
        workout_id: int | None,
        exercise_id: str,
        metric_type: str,
        reps: int | None,
        duration_seconds: int | None,
        distance_m: float | None,
        calories: float | None,
        steps: int | None,
        avg_heart_rate: float | None,
        max_heart_rate: float | None,
        avg_power_watts: float | None,
        max_power_watts: float | None,
        avg_speed_mps: float | None,
        intensity: str | None,
        source: str | None,
        notes: str | None,
        created_at: datetime | None,
        equipment_id: str | None,
        added_weight: float | None,
    ) -> int:
        resolved_metric_type = _normalize_metric_type(metric_type)
        if resolved_metric_type == METRIC_TYPE_STRENGTH:
            raise ValueError(
                "Use save_current_set or add_set_to_workout for strength sets."
            )

        with self._connect() as conn:
            exercise_row = conn.execute(
                "SELECT id, name_en, name_de FROM exercises WHERE id = ? LIMIT 1",
                (exercise_id,),
            ).fetchone()
            if exercise_row is None:
                raise ValueError(f"Exercise '{exercise_id}' not found")
            exercise_display = str(
                exercise_row["name_en"] or exercise_row["name_de"] or exercise_id
            )
            effective_created_at = created_at or datetime.now(timezone.utc)

            resolved_duration_seconds = (
                int(duration_seconds) if duration_seconds is not None else None
            )
            resolved_distance_m = float(distance_m) if distance_m is not None else None
            resolved_calories = float(calories) if calories is not None else None
            resolved_steps = int(steps) if steps is not None else None
            resolved_avg_hr = float(avg_heart_rate) if avg_heart_rate is not None else None
            resolved_max_hr = float(max_heart_rate) if max_heart_rate is not None else None
            resolved_avg_power = (
                float(avg_power_watts) if avg_power_watts is not None else None
            )
            resolved_max_power = (
                float(max_power_watts) if max_power_watts is not None else None
            )
            resolved_avg_speed = (
                float(avg_speed_mps) if avg_speed_mps is not None else None
            )
            resolved_added_weight = (
                float(added_weight) if added_weight is not None else None
            )

            resolved_reps = 0
            weight = 0.0
            volume = 0.0
            load_score = 0.0

            if resolved_metric_type == METRIC_TYPE_BODYWEIGHT:
                resolved_reps = int(reps) if reps is not None else 1
                if resolved_reps < 1:
                    raise ValueError("reps must be >= 1 for bodyweight metric type")
                if resolved_added_weight is not None and resolved_added_weight > 0:
                    weight = resolved_added_weight
                    volume = resolved_added_weight * resolved_reps
                load_score = float(resolved_reps)
            elif resolved_metric_type in (METRIC_TYPE_DURATION, METRIC_TYPE_HOLD):
                if resolved_duration_seconds is None or resolved_duration_seconds <= 0:
                    raise ValueError("duration_seconds must be > 0 for this metric type")
                load_score = float(resolved_duration_seconds) / 60.0
            elif resolved_metric_type == METRIC_TYPE_DISTANCE:
                if resolved_distance_m is None or resolved_distance_m <= 0:
                    raise ValueError("distance_m must be > 0 for distance metric type")
                if resolved_duration_seconds is not None and resolved_duration_seconds > 0:
                    load_score = float(resolved_duration_seconds) / 60.0
                else:
                    load_score = float(resolved_distance_m) / 1000.0
            elif resolved_metric_type == METRIC_TYPE_CARDIO:
                if resolved_duration_seconds is None or resolved_duration_seconds <= 0:
                    raise ValueError("duration_seconds must be > 0 for cardio metric type")
                intensity_factor = _cardio_intensity_factor(intensity)
                load_score = (float(resolved_duration_seconds) / 60.0) * intensity_factor
            elif resolved_metric_type == METRIC_TYPE_CUSTOM:
                load_score = 0.0

            cursor = conn.execute(
                """
                INSERT INTO set_logs(
                    user_id, workout_id, exercise, exercise_id, equipment_id, metric_type,
                    weight, reps, volume, notes, created_at, updated_at,
                    duration_seconds, distance_m, calories, steps, avg_heart_rate, max_heart_rate,
                    avg_power_watts, max_power_watts, avg_speed_mps, load_score, intensity, source, added_weight
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    workout_id,
                    exercise_display,
                    exercise_id,
                    equipment_id,
                    resolved_metric_type,
                    weight,
                    resolved_reps,
                    volume,
                    notes,
                    _isoformat(effective_created_at),
                    _isoformat(datetime.now(timezone.utc)),
                    resolved_duration_seconds,
                    resolved_distance_m,
                    resolved_calories,
                    resolved_steps,
                    resolved_avg_hr,
                    resolved_max_hr,
                    resolved_avg_power,
                    resolved_max_power,
                    resolved_avg_speed,
                    load_score,
                    intensity,
                    source,
                    resolved_added_weight,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def _get_workouts(self, user_id: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
        query_limit = max(1, int(limit))
        query_offset = max(0, int(offset))
        with self._connect() as conn:
            where_sql = ""
            params: tuple[Any, ...] = ()
            if user_id is not None:
                where_sql = "WHERE w.user_id = ?"
                params = (user_id,)
            rows = conn.execute(
                f"""
                SELECT
                    w.id,
                    w.user_id,
                    w.started_at,
                    COALESCE(w.ended_at, w.finished_at) AS ended_at,
                    COALESCE(w.status, CASE WHEN COALESCE(w.ended_at, w.finished_at) IS NULL THEN 'active' ELSE 'completed' END) AS status,
                    w.notes,
                    w.created_at,
                    w.updated_at,
                    COALESCE(SUM(sl.volume), 0) AS total_volume,
                    COUNT(sl.id) AS total_sets,
                    COUNT(DISTINCT sl.exercise_id) AS exercise_count,
                    COUNT(DISTINCT sl.equipment_id) AS equipment_count
                FROM workouts w
                LEFT JOIN set_logs sl ON sl.workout_id = w.id
                {where_sql}
                GROUP BY w.id, w.user_id, w.started_at, w.ended_at, w.finished_at, w.status, w.notes, w.created_at, w.updated_at
                ORDER BY w.started_at DESC, w.id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, query_limit, query_offset),
            ).fetchall()
            return [_row_to_dict(row) for row in rows if row is not None]

    def _get_workout(self, workout_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    w.id,
                    w.user_id,
                    w.started_at,
                    COALESCE(w.ended_at, w.finished_at) AS ended_at,
                    COALESCE(w.status, CASE WHEN COALESCE(w.ended_at, w.finished_at) IS NULL THEN 'active' ELSE 'completed' END) AS status,
                    w.notes,
                    w.created_at,
                    w.updated_at
                FROM workouts w
                WHERE w.id = ?
                LIMIT 1
                """,
                (int(workout_id),),
            ).fetchone()
            return _row_to_dict(row)

    def _create_workout(
        self,
        user_id: str,
        started_at: datetime,
        ended_at: datetime | None,
        notes: str | None,
        status: str,
    ) -> dict[str, Any]:
        started_iso = _isoformat(started_at)
        ended_iso = _isoformat(ended_at) if ended_at is not None else None
        now_iso = _isoformat(datetime.now(timezone.utc))
        normalized_status = (
            str(status).strip().lower()
            if isinstance(status, str) and str(status).strip()
            else ("active" if ended_iso is None else "completed")
        )
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO workouts(
                    user_id, started_at, finished_at, ended_at, status, notes, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    started_iso,
                    ended_iso,
                    ended_iso,
                    normalized_status,
                    notes,
                    now_iso,
                    now_iso,
                ),
            )
            workout_id = int(cursor.lastrowid)
            conn.commit()
        row = self._get_workout(workout_id)
        if row is None:
            raise ValueError(f"Workout {workout_id} not found after create")
        return row

    def _update_workout(
        self,
        workout_id: int,
        started_at: datetime | None,
        ended_at: datetime | None,
        notes: str | None,
        status: str | None,
    ) -> dict[str, Any]:
        workout_id = int(workout_id)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id, started_at, ended_at, finished_at, status, notes FROM workouts WHERE id = ?",
                (workout_id,),
            ).fetchone()
            if existing is None:
                raise ValueError(f"Workout {workout_id} not found")

            existing_started = _parse_iso_datetime(existing["started_at"])
            existing_ended = _parse_iso_datetime(existing["ended_at"] or existing["finished_at"])
            new_started = started_at or existing_started
            new_ended = ended_at if ended_at is not None else existing_ended
            if new_started is not None and new_ended is not None and new_started > new_ended:
                raise ValueError("started_at must be before or equal to ended_at")

            updates: list[str] = []
            params: list[Any] = []
            if started_at is not None:
                updates.append("started_at = ?")
                params.append(_isoformat(started_at))
            if ended_at is not None:
                ended_iso = _isoformat(ended_at)
                updates.append("ended_at = ?")
                updates.append("finished_at = ?")
                params.extend([ended_iso, ended_iso])
            if notes is not None:
                updates.append("notes = ?")
                params.append(notes)
            if status is not None:
                updates.append("status = ?")
                params.append(str(status).strip().lower())
            if not updates:
                raise ValueError("No workout update fields provided")

            updates.append("updated_at = ?")
            params.append(_isoformat(datetime.now(timezone.utc)))
            params.append(workout_id)
            conn.execute(
                f"UPDATE workouts SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
            conn.commit()
        row = self._get_workout(workout_id)
        if row is None:
            raise ValueError(f"Workout {workout_id} not found after update")
        return row

    def _delete_workout(self, workout_id: int, delete_sets: bool) -> None:
        workout_id = int(workout_id)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM workouts WHERE id = ?",
                (workout_id,),
            ).fetchone()
            if existing is None:
                raise ValueError(f"Workout {workout_id} not found")
            if delete_sets:
                conn.execute("DELETE FROM set_logs WHERE workout_id = ?", (workout_id,))
            else:
                conn.execute("UPDATE set_logs SET workout_id = NULL WHERE workout_id = ?", (workout_id,))
            conn.execute("DELETE FROM workouts WHERE id = ?", (workout_id,))
            conn.commit()

    def _get_sets_for_workout(self, workout_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    sl.id,
                    sl.workout_id,
                    sl.user_id,
                    sl.equipment_id,
                    eq.name AS equipment_name,
                    eq.name_en AS equipment_name_en,
                    eq.name_de AS equipment_name_de,
                    sl.exercise_id,
                    ex.name_en AS exercise_name_en,
                    ex.name_de AS exercise_name_de,
                    sl.exercise,
                    sl.metric_type,
                    sl.weight,
                    sl.reps,
                    sl.volume,
                    sl.duration_seconds,
                    sl.distance_m,
                    sl.calories,
                    sl.steps,
                    sl.avg_heart_rate,
                    sl.max_heart_rate,
                    sl.avg_power_watts,
                    sl.max_power_watts,
                    sl.avg_speed_mps,
                    sl.load_score,
                    sl.intensity,
                    sl.source,
                    sl.added_weight,
                    sl.notes,
                    sl.created_at,
                    sl.updated_at
                FROM set_logs sl
                LEFT JOIN equipment eq ON eq.id = sl.equipment_id
                LEFT JOIN exercises ex ON ex.id = sl.exercise_id
                WHERE sl.workout_id = ?
                ORDER BY sl.created_at ASC, sl.id ASC
                """,
                (int(workout_id),),
            ).fetchall()
            return [_row_to_dict(row) for row in rows if row is not None]

    def _add_set_to_workout(
        self,
        workout_id: int,
        user_id: str,
        equipment_id: str | None,
        exercise_id: str,
        weight: float,
        reps: int,
        notes: str | None,
        created_at: datetime | None,
    ) -> dict[str, Any]:
        workout_id = int(workout_id)
        resolved_weight = float(weight)
        resolved_reps = int(reps)
        volume = resolved_weight * resolved_reps
        with self._connect() as conn:
            workout_row = conn.execute(
                "SELECT id, started_at FROM workouts WHERE id = ?",
                (workout_id,),
            ).fetchone()
            if workout_row is None:
                raise ValueError(f"Workout {workout_id} not found")

            exercise_row = conn.execute(
                "SELECT id, name_en, name_de, metric_type FROM exercises WHERE id = ?",
                (exercise_id,),
            ).fetchone()
            if exercise_row is None:
                raise ValueError(f"Exercise '{exercise_id}' not found")

            resolved_created_at = (
                _isoformat(created_at)
                if created_at is not None
                else str(workout_row["started_at"] or _isoformat(datetime.now(timezone.utc)))
            )
            resolved_updated_at = _isoformat(datetime.now(timezone.utc))
            exercise_display = str(
                exercise_row["name_en"] or exercise_row["name_de"] or exercise_id
            )
            metric_type = _normalize_metric_type(exercise_row["metric_type"])
            cursor = conn.execute(
                """
                INSERT INTO set_logs(
                    workout_id, user_id, equipment_id, exercise_id, exercise, metric_type,
                    weight, reps, volume, notes, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workout_id,
                    user_id,
                    equipment_id,
                    exercise_id,
                    exercise_display,
                    metric_type,
                    resolved_weight,
                    resolved_reps,
                    volume,
                    notes,
                    resolved_created_at,
                    resolved_updated_at,
                ),
            )
            set_id = int(cursor.lastrowid)
            conn.commit()
        rows = self._get_sets_for_workout(workout_id)
        for row in rows:
            if int(row.get("id", -1)) == set_id:
                return row
        raise ValueError(f"Set {set_id} not found after create")

    def _update_set(
        self,
        set_id: int,
        equipment_id: str | None,
        exercise_id: str | None,
        weight: float | None,
        reps: int | None,
        notes: str | None,
        created_at: datetime | None,
    ) -> dict[str, Any]:
        set_id = int(set_id)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id, workout_id, equipment_id, exercise_id, exercise, metric_type,
                    weight, reps, volume, notes, created_at, updated_at,
                    duration_seconds, distance_m, calories, steps, avg_heart_rate, max_heart_rate,
                    avg_power_watts, max_power_watts, avg_speed_mps, load_score, intensity, source, added_weight
                FROM set_logs
                WHERE id = ?
                LIMIT 1
                """,
                (set_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Set {set_id} not found")

            updates: list[str] = []
            params: list[Any] = []
            resolved_exercise_id = str(row["exercise_id"] or "")
            resolved_exercise_display = str(row["exercise"] or resolved_exercise_id)
            resolved_metric_type = _normalize_metric_type(row["metric_type"])
            if exercise_id is not None:
                exercise_row = conn.execute(
                    "SELECT id, name_en, name_de, metric_type FROM exercises WHERE id = ?",
                    (exercise_id,),
                ).fetchone()
                if exercise_row is None:
                    raise ValueError(f"Exercise '{exercise_id}' not found")
                resolved_exercise_id = str(exercise_row["id"])
                resolved_exercise_display = str(
                    exercise_row["name_en"] or exercise_row["name_de"] or resolved_exercise_id
                )
                resolved_metric_type = _normalize_metric_type(exercise_row["metric_type"])
                updates.append("exercise_id = ?")
                params.append(resolved_exercise_id)
                updates.append("exercise = ?")
                params.append(resolved_exercise_display)
                updates.append("metric_type = ?")
                params.append(resolved_metric_type)

            if equipment_id is not None:
                updates.append("equipment_id = ?")
                params.append(equipment_id)

            resolved_weight = float(weight) if weight is not None else float(row["weight"])
            resolved_reps = int(reps) if reps is not None else int(row["reps"])
            if weight is not None:
                updates.append("weight = ?")
                params.append(resolved_weight)
            if reps is not None:
                updates.append("reps = ?")
                params.append(resolved_reps)
            if (weight is not None or reps is not None) and resolved_metric_type == METRIC_TYPE_STRENGTH:
                updates.append("volume = ?")
                params.append(float(resolved_weight * resolved_reps))

            if notes is not None:
                updates.append("notes = ?")
                params.append(notes)
            if created_at is not None:
                updates.append("created_at = ?")
                params.append(_isoformat(created_at))

            if not updates:
                raise ValueError("No set update fields provided")

            updates.append("updated_at = ?")
            params.append(_isoformat(datetime.now(timezone.utc)))
            params.append(set_id)
            conn.execute(
                f"UPDATE set_logs SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
            conn.commit()

            updated = conn.execute(
                """
                SELECT
                    sl.id,
                    sl.workout_id,
                    sl.user_id,
                    sl.equipment_id,
                    eq.name AS equipment_name,
                    eq.name_en AS equipment_name_en,
                    eq.name_de AS equipment_name_de,
                    sl.exercise_id,
                    ex.name_en AS exercise_name_en,
                    ex.name_de AS exercise_name_de,
                    sl.exercise,
                    sl.metric_type,
                    sl.weight,
                    sl.reps,
                    sl.volume,
                    sl.duration_seconds,
                    sl.distance_m,
                    sl.calories,
                    sl.steps,
                    sl.avg_heart_rate,
                    sl.max_heart_rate,
                    sl.avg_power_watts,
                    sl.max_power_watts,
                    sl.avg_speed_mps,
                    sl.load_score,
                    sl.intensity,
                    sl.source,
                    sl.added_weight,
                    sl.notes,
                    sl.created_at,
                    sl.updated_at
                FROM set_logs sl
                LEFT JOIN equipment eq ON eq.id = sl.equipment_id
                LEFT JOIN exercises ex ON ex.id = sl.exercise_id
                WHERE sl.id = ?
                LIMIT 1
                """,
                (set_id,),
            ).fetchone()
            if updated is None:
                raise ValueError(f"Set {set_id} not found after update")
            return _row_to_dict(updated) or {}

    def _delete_set(self, set_id: int) -> None:
        set_id = int(set_id)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM set_logs WHERE id = ?",
                (set_id,),
            ).fetchone()
            if existing is None:
                raise ValueError(f"Set {set_id} not found")
            conn.execute("DELETE FROM set_logs WHERE id = ?", (set_id,))
            conn.commit()

    def _get_total_volume(self, user_id: str | None) -> float:
        sql = "SELECT COALESCE(SUM(volume), 0) AS value FROM set_logs"
        params: tuple[Any, ...] = ()
        if user_id is not None:
            sql += " WHERE user_id = ?"
            params = (user_id,)
        return self._read_float(sql, params)

    def _get_total_volume_by_exercise(self, exercise_id: str, user_id: str | None) -> float:
        with self._connect() as conn:
            where_sql, where_params = self._exercise_predicate(conn, exercise_id)
            sql = f"SELECT COALESCE(SUM(volume), 0) AS value FROM set_logs WHERE {where_sql}"
            params: tuple[Any, ...] = where_params
            if user_id is not None:
                sql += " AND user_id = ?"
                params = (*params, user_id)
            row = conn.execute(sql, params).fetchone()
            return float(row["value"] if row is not None else 0.0)

    def _get_pr_by_exercise(self, exercise_id: str, user_id: str | None) -> float:
        with self._connect() as conn:
            where_sql, where_params = self._exercise_predicate(conn, exercise_id)
            sql = (
                f"SELECT COALESCE(MAX(weight), 0) AS value FROM set_logs "
                f"WHERE {where_sql} AND COALESCE(metric_type, '{DEFAULT_METRIC_TYPE}') = '{METRIC_TYPE_STRENGTH}'"
            )
            params: tuple[Any, ...] = where_params
            if user_id is not None:
                sql += " AND user_id = ?"
                params = (*params, user_id)
            row = conn.execute(sql, params).fetchone()
            return float(row["value"] if row is not None else 0.0)

    def _get_set_count(self, user_id: str | None) -> int:
        sql = "SELECT COUNT(*) AS value FROM set_logs"
        params: tuple[Any, ...] = ()
        if user_id is not None:
            sql += " WHERE user_id = ?"
            params = (user_id,)
        return self._read_int(sql, params)

    def _get_set_count_for_workout(self, workout_id: int) -> int:
        return self._read_int("SELECT COUNT(*) AS value FROM set_logs WHERE workout_id = ?", (workout_id,))

    def _get_workout_count(self, user_id: str | None) -> int:
        sql = "SELECT COUNT(*) AS value FROM workouts"
        params: tuple[Any, ...] = ()
        if user_id is not None:
            sql += " WHERE user_id = ?"
            params = (user_id,)
        return self._read_int(sql, params)

    def _get_recent_sets(self, limit: int, user_id: str | None) -> list[dict[str, Any]]:
        sql = """
            SELECT
                id, user_id, workout_id, exercise, exercise_id, equipment_id, metric_type,
                weight, reps, volume, notes, created_at, updated_at,
                duration_seconds, distance_m, calories, steps, avg_heart_rate, max_heart_rate,
                avg_power_watts, max_power_watts, avg_speed_mps, load_score, intensity, source, added_weight
            FROM set_logs
        """
        params: tuple[Any, ...] = ()
        if user_id is not None:
            sql += " WHERE user_id = ?"
            params = (user_id,)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params = (*params, limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [_row_to_dict(row) for row in rows if row is not None]

    def _upsert_user(self, user_id: str, display_name: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users(id, display_name, enabled, created_at)
                VALUES(?, ?, 1, ?)
                ON CONFLICT(id) DO UPDATE SET
                    display_name = CASE
                        WHEN excluded.display_name IS NOT NULL AND excluded.display_name != ''
                            THEN excluded.display_name
                        ELSE users.display_name
                    END,
                    enabled = 1
                """,
                (user_id, display_name, _isoformat(datetime.now(timezone.utc))),
            )
            conn.commit()

    def _get_users(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, display_name, enabled, created_at
                FROM users
                ORDER BY COALESCE(display_name, id) ASC
                """
            ).fetchall()
            return [_row_to_dict(row) for row in rows if row is not None]

    def _get_user(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, display_name, enabled, created_at
                FROM users
                WHERE id = ?
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            return _row_to_dict(row)

    def _get_exercises(self, enabled_only: bool) -> list[dict[str, Any]]:
        sql = """
            SELECT id, name_en, name_de, muscle_group, equipment, equipment_id, metric_type,
                   enabled, sort_order, uses_bodyweight, bodyweight_factor, created_at
            FROM exercises
        """
        params: tuple[Any, ...] = ()
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY enabled DESC, sort_order ASC, name_en COLLATE NOCASE ASC, id ASC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [_row_to_dict(row) for row in rows if row is not None]

    def _get_exercise(self, exercise_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, name_en, name_de, muscle_group, equipment, equipment_id, metric_type,
                       enabled, sort_order, uses_bodyweight, bodyweight_factor, created_at
                FROM exercises
                WHERE id = ?
                LIMIT 1
                """,
                (exercise_id,),
            ).fetchone()
            if row is None:
                return None
            return _row_to_dict(row)

    def _get_exercise_metric_type(self, exercise_id: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT metric_type FROM exercises WHERE id = ? LIMIT 1",
                (exercise_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Exercise '{exercise_id}' not found")
            return _normalize_metric_type(row["metric_type"])

    def _get_set_log(self, set_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id, user_id, workout_id, exercise, exercise_id, equipment_id, metric_type,
                    weight, reps, volume, notes, created_at, updated_at,
                    duration_seconds, distance_m, calories, steps, avg_heart_rate, max_heart_rate,
                    avg_power_watts, max_power_watts, avg_speed_mps, load_score, intensity, source, added_weight
                FROM set_logs
                WHERE id = ?
                LIMIT 1
                """,
                (int(set_id),),
            ).fetchone()
            return _row_to_dict(row)

    def _add_exercise(
        self,
        exercise_id: str,
        name_en: str,
        name_de: str | None,
        muscle_group: str | None,
        equipment: str | None,
        equipment_id: str | None,
        metric_type: str | None,
        enabled: bool,
        sort_order: int,
        uses_bodyweight: bool = False,
        bodyweight_factor: float = 1.0,
    ) -> None:
        resolved_metric_type = _normalize_metric_type(metric_type)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO exercises(
                    id, name_en, name_de, muscle_group, equipment, equipment_id, metric_type,
                    enabled, sort_order, uses_bodyweight, bodyweight_factor, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name_en = excluded.name_en,
                    name_de = excluded.name_de,
                    muscle_group = excluded.muscle_group,
                    equipment = excluded.equipment,
                    equipment_id = COALESCE(excluded.equipment_id, exercises.equipment_id),
                    metric_type = excluded.metric_type,
                    enabled = excluded.enabled,
                    sort_order = excluded.sort_order,
                    uses_bodyweight = excluded.uses_bodyweight,
                    bodyweight_factor = excluded.bodyweight_factor
                """,
                (
                    exercise_id,
                    name_en,
                    name_de,
                    muscle_group,
                    equipment,
                    equipment_id,
                    resolved_metric_type,
                    1 if enabled else 0,
                    sort_order,
                    1 if uses_bodyweight else 0,
                    bodyweight_factor,
                    _isoformat(datetime.now(timezone.utc)),
                ),
            )
            conn.commit()

    def _update_exercise(
        self,
        exercise_id: str,
        name_en: str | None,
        name_de: str | None,
        muscle_group: str | None,
        equipment: str | None,
        equipment_id: str | None,
        metric_type: str | None,
        enabled: bool | None,
        sort_order: int | None,
        uses_bodyweight: bool | None = None,
        bodyweight_factor: float | None = None,
    ) -> bool:
        updates: list[str] = []
        params: list[Any] = []
        if name_en is not None:
            updates.append("name_en = ?")
            params.append(name_en)
        if name_de is not None:
            updates.append("name_de = ?")
            params.append(name_de)
        if muscle_group is not None:
            updates.append("muscle_group = ?")
            params.append(muscle_group)
        if equipment is not None:
            updates.append("equipment = ?")
            params.append(equipment)
        if equipment_id is not None:
            updates.append("equipment_id = ?")
            params.append(equipment_id)
        if metric_type is not None:
            updates.append("metric_type = ?")
            params.append(_normalize_metric_type(metric_type))
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)
        if sort_order is not None:
            updates.append("sort_order = ?")
            params.append(sort_order)
        if uses_bodyweight is not None:
            updates.append("uses_bodyweight = ?")
            params.append(1 if uses_bodyweight else 0)
        if bodyweight_factor is not None:
            updates.append("bodyweight_factor = ?")
            params.append(bodyweight_factor)
        if not updates:
            return False

        params.append(exercise_id)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE exercises SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
            conn.commit()
            return int(cursor.rowcount) > 0

    def _disable_exercise(self, exercise_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("UPDATE exercises SET enabled = 0 WHERE id = ?", (exercise_id,))
            conn.commit()
            return int(cursor.rowcount) > 0

    def _refresh_exercises(self) -> None:
        with self._connect() as conn:
            now = _isoformat(datetime.now(timezone.utc))
            for exercise in DEFAULT_EXERCISES:
                conn.execute(
                    """
                    INSERT INTO exercises(
                        id, name_en, name_de, muscle_group, equipment, equipment_id, metric_type, enabled, sort_order, created_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name_en = excluded.name_en,
                        name_de = excluded.name_de,
                        muscle_group = excluded.muscle_group,
                        equipment = excluded.equipment,
                        equipment_id = COALESCE(exercises.equipment_id, excluded.equipment_id),
                        metric_type = COALESCE(exercises.metric_type, excluded.metric_type),
                        sort_order = excluded.sort_order,
                        enabled = 1
                    """,
                    (
                        str(exercise["id"]),
                        str(exercise["name_en"]),
                        exercise["name_de"],
                        exercise["muscle_group"],
                        exercise["equipment"],
                        DEFAULT_EXERCISE_EQUIPMENT_MAP.get(str(exercise["id"])),
                        DEFAULT_METRIC_TYPE,
                        int(exercise["sort_order"]),
                        now,
                    ),
                )
            conn.commit()

    def _add_equipment(
        self,
        equipment_id: str,
        name: str | None,
        name_en: str | None,
        name_de: str | None,
        description: str | None,
        icon: str | None,
        location: str | None,
        enabled: bool,
        sort_order: int,
    ) -> None:
        resolved_name_en, resolved_name_de, resolved_name = _resolve_equipment_names(
            name=name,
            name_en=name_en,
            name_de=name_de,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO equipment(id, name, name_en, name_de, description, icon, location, enabled, sort_order, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    name_en = excluded.name_en,
                    name_de = excluded.name_de,
                    description = excluded.description,
                    icon = excluded.icon,
                    location = excluded.location,
                    enabled = excluded.enabled,
                    sort_order = excluded.sort_order
                """,
                (
                    equipment_id,
                    resolved_name,
                    resolved_name_en,
                    resolved_name_de,
                    description,
                    icon,
                    location,
                    1 if enabled else 0,
                    sort_order,
                    _isoformat(datetime.now(timezone.utc)),
                ),
            )
            conn.commit()

    def _update_equipment(
        self,
        equipment_id: str,
        name: str | None,
        name_en: str | None,
        name_de: str | None,
        description: str | None,
        icon: str | None,
        location: str | None,
        enabled: bool | None,
        sort_order: int | None,
    ) -> bool:
        updates: list[str] = []
        params: list[Any] = []
        if name is not None or name_en is not None or name_de is not None:
            resolved_name_en, resolved_name_de, resolved_name = _resolve_equipment_names(
                name=name,
                name_en=name_en,
                name_de=name_de,
                existing=self._get_equipment(equipment_id),
            )
            updates.append("name_en = ?")
            params.append(resolved_name_en)
            updates.append("name_de = ?")
            params.append(resolved_name_de)
            updates.append("name = ?")
            params.append(resolved_name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if icon is not None:
            updates.append("icon = ?")
            params.append(icon)
        if location is not None:
            updates.append("location = ?")
            params.append(location)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)
        if sort_order is not None:
            updates.append("sort_order = ?")
            params.append(sort_order)
        if not updates:
            return False

        params.append(equipment_id)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE equipment SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
            conn.commit()
            return int(cursor.rowcount) > 0

    def _disable_equipment(self, equipment_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("UPDATE equipment SET enabled = 0 WHERE id = ?", (equipment_id,))
            conn.commit()
            return int(cursor.rowcount) > 0

    def _get_equipment(self, equipment_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, name, name_en, name_de, description, icon, location, enabled, sort_order, created_at
                FROM equipment
                WHERE id = ?
                LIMIT 1
                """,
                (equipment_id,),
            ).fetchone()
            return _row_to_dict(row)

    def _get_all_equipment(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self._seed_default_equipment(conn)
            rows = conn.execute(
                """
                SELECT id, name, name_en, name_de, description, icon, location, enabled, sort_order, created_at
                FROM equipment
                ORDER BY enabled DESC, sort_order ASC, COALESCE(name_de, name_en, name, id) COLLATE NOCASE ASC, id ASC
                """
            ).fetchall()
            return [_row_to_dict(row) for row in rows if row is not None]

    def _get_enabled_equipment(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self._seed_default_equipment(conn)
            rows = conn.execute(
                """
                SELECT id, name, name_en, name_de, description, icon, location, enabled, sort_order, created_at
                FROM equipment
                WHERE enabled = 1
                ORDER BY sort_order ASC, COALESCE(name_de, name_en, name, id) COLLATE NOCASE ASC, id ASC
                """
            ).fetchall()
            return [_row_to_dict(row) for row in rows if row is not None]

    def _assign_exercise_to_equipment(self, exercise_id: str, equipment_id: str | None) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE exercises SET equipment_id = ? WHERE id = ?",
                (equipment_id, exercise_id),
            )
            conn.commit()
            return int(cursor.rowcount) > 0

    def _get_exercises_for_equipment(
        self, equipment_id: str | None, enabled_only: bool
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT id, name_en, name_de, muscle_group, equipment, equipment_id, metric_type, enabled, sort_order, created_at
            FROM exercises
        """
        params: tuple[Any, ...] = ()
        filters: list[str] = []
        if enabled_only:
            filters.append("enabled = 1")
        if equipment_id is not None:
            filters.append("equipment_id = ?")
            params = (equipment_id,)
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        sql += " ORDER BY sort_order ASC, name_en COLLATE NOCASE ASC, id ASC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [_row_to_dict(row) for row in rows if row is not None]

    def _get_muscle_groups(self, enabled_only: bool) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self._seed_default_muscle_groups(conn)
            sql = """
                SELECT
                    id, name_en, name_de, description, icon, body_region,
                    enabled, sort_order, created_at, updated_at
                FROM muscle_groups
            """
            if enabled_only:
                sql += " WHERE enabled = 1"
            sql += " ORDER BY enabled DESC, sort_order ASC, name_en COLLATE NOCASE ASC, id ASC"
            rows = conn.execute(sql).fetchall()
            return [_row_to_dict(row) for row in rows if row is not None]

    def _get_muscle_group(self, muscle_group_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id, name_en, name_de, description, icon, body_region,
                    enabled, sort_order, created_at, updated_at
                FROM muscle_groups
                WHERE id = ?
                LIMIT 1
                """,
                (muscle_group_id,),
            ).fetchone()
            return _row_to_dict(row)

    def _add_muscle_group(
        self,
        muscle_group_id: str,
        name_en: str,
        name_de: str | None,
        description: str | None,
        icon: str | None,
        body_region: str | None,
        enabled: bool,
        sort_order: int,
    ) -> None:
        now = _isoformat(datetime.now(timezone.utc))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO muscle_groups(
                    id, name_en, name_de, description, icon, body_region,
                    enabled, sort_order, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name_en = excluded.name_en,
                    name_de = excluded.name_de,
                    description = excluded.description,
                    icon = excluded.icon,
                    body_region = excluded.body_region,
                    enabled = excluded.enabled,
                    sort_order = excluded.sort_order,
                    updated_at = excluded.updated_at
                """,
                (
                    muscle_group_id,
                    name_en,
                    name_de,
                    description,
                    icon,
                    body_region,
                    1 if enabled else 0,
                    sort_order,
                    now,
                    now,
                ),
            )
            conn.commit()

    def _update_muscle_group(
        self,
        muscle_group_id: str,
        name_en: str | None,
        name_de: str | None,
        description: str | None,
        icon: str | None,
        body_region: str | None,
        enabled: bool | None,
        sort_order: int | None,
    ) -> bool:
        updates: list[str] = []
        params: list[Any] = []
        if name_en is not None:
            updates.append("name_en = ?")
            params.append(name_en)
        if name_de is not None:
            updates.append("name_de = ?")
            params.append(name_de)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if icon is not None:
            updates.append("icon = ?")
            params.append(icon)
        if body_region is not None:
            updates.append("body_region = ?")
            params.append(body_region)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)
        if sort_order is not None:
            updates.append("sort_order = ?")
            params.append(sort_order)
        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(_isoformat(datetime.now(timezone.utc)))
        params.append(muscle_group_id)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE muscle_groups SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
            conn.commit()
            return int(cursor.rowcount) > 0

    def _disable_muscle_group(self, muscle_group_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE muscle_groups
                SET enabled = 0, updated_at = ?
                WHERE id = ?
                """,
                (_isoformat(datetime.now(timezone.utc)), muscle_group_id),
            )
            conn.commit()
            return int(cursor.rowcount) > 0

    def _assign_muscle_group_to_exercise(
        self,
        exercise_id: str,
        muscle_group_id: str,
        role: str,
        weight_factor: float,
    ) -> None:
        normalized_role = _normalize_muscle_role(role)
        resolved_factor = _resolve_weight_factor(normalized_role, weight_factor)
        now = _isoformat(datetime.now(timezone.utc))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO exercise_muscle_groups(
                    exercise_id, muscle_group_id, role, weight_factor, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(exercise_id, muscle_group_id) DO UPDATE SET
                    role = excluded.role,
                    weight_factor = excluded.weight_factor,
                    updated_at = excluded.updated_at
                """,
                (
                    exercise_id,
                    muscle_group_id,
                    normalized_role,
                    resolved_factor,
                    now,
                    now,
                ),
            )
            conn.commit()

    def _remove_muscle_group_from_exercise(
        self, exercise_id: str, muscle_group_id: str
    ) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM exercise_muscle_groups
                WHERE exercise_id = ? AND muscle_group_id = ?
                """,
                (exercise_id, muscle_group_id),
            )
            conn.commit()
            return int(cursor.rowcount) > 0

    def _replace_muscle_groups_for_exercise(
        self,
        exercise_id: str,
        primary_ids: list[str],
        secondary_ids: list[str],
        stabilizer_ids: list[str],
    ) -> None:
        now = _isoformat(datetime.now(timezone.utc))
        rows: list[tuple[str, str, float]] = []
        for muscle_group_id in primary_ids:
            rows.append((muscle_group_id, MUSCLE_ROLE_PRIMARY, DEFAULT_MUSCLE_ROLE_WEIGHT_FACTORS[MUSCLE_ROLE_PRIMARY]))
        for muscle_group_id in secondary_ids:
            rows.append((muscle_group_id, MUSCLE_ROLE_SECONDARY, DEFAULT_MUSCLE_ROLE_WEIGHT_FACTORS[MUSCLE_ROLE_SECONDARY]))
        for muscle_group_id in stabilizer_ids:
            rows.append((muscle_group_id, MUSCLE_ROLE_STABILIZER, DEFAULT_MUSCLE_ROLE_WEIGHT_FACTORS[MUSCLE_ROLE_STABILIZER]))

        dedup: dict[str, tuple[str, float]] = {}
        for muscle_group_id, role, factor in rows:
            normalized_id = str(muscle_group_id).strip()
            if not normalized_id:
                continue
            dedup[normalized_id] = (role, factor)

        with self._connect() as conn:
            conn.execute(
                "DELETE FROM exercise_muscle_groups WHERE exercise_id = ?",
                (exercise_id,),
            )
            for muscle_group_id, (role, factor) in dedup.items():
                conn.execute(
                    """
                    INSERT INTO exercise_muscle_groups(
                        exercise_id, muscle_group_id, role, weight_factor, created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (exercise_id, muscle_group_id, role, factor, now, now),
                )
            conn.commit()

    def _get_muscle_groups_for_exercise(self, exercise_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    emg.exercise_id,
                    emg.muscle_group_id,
                    emg.role,
                    emg.weight_factor,
                    emg.created_at,
                    emg.updated_at,
                    mg.name_en,
                    mg.name_de,
                    mg.icon,
                    mg.body_region,
                    mg.enabled
                FROM exercise_muscle_groups emg
                LEFT JOIN muscle_groups mg ON mg.id = emg.muscle_group_id
                WHERE emg.exercise_id = ?
                ORDER BY
                    CASE emg.role
                        WHEN 'primary' THEN 1
                        WHEN 'secondary' THEN 2
                        ELSE 3
                    END,
                    emg.weight_factor DESC,
                    emg.muscle_group_id ASC
                """,
                (exercise_id,),
            ).fetchall()
            return [_row_to_dict(row) for row in rows if row is not None]

    def _get_exercises_for_muscle_group(self, muscle_group_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    emg.exercise_id,
                    emg.role,
                    emg.weight_factor,
                    ex.name_en,
                    ex.name_de,
                    ex.enabled,
                    ex.equipment_id
                FROM exercise_muscle_groups emg
                LEFT JOIN exercises ex ON ex.id = emg.exercise_id
                WHERE emg.muscle_group_id = ?
                ORDER BY
                    CASE emg.role
                        WHEN 'primary' THEN 1
                        WHEN 'secondary' THEN 2
                        ELSE 3
                    END,
                    emg.weight_factor DESC,
                    emg.exercise_id ASC
                """,
                (muscle_group_id,),
            ).fetchall()
            return [_row_to_dict(row) for row in rows if row is not None]

    def _replace_muscle_groups_with_weights(
        self,
        exercise_id: str,
        mappings: list[dict[str, Any]],
    ) -> None:
        """Replace all muscle-group mappings for one exercise with explicit weight factors.

        Validates and normalizes so that the sum of weight_factors equals 1.0 (± tolerance).
        Raises ValueError on validation failure.
        """
        # --- Validation ---
        if not mappings:
            raise ValueError("muscle_group_mapping_empty")

        seen_ids: set[str] = set()
        validated_rows: list[tuple[str, str, float]] = []
        for mapping in mappings:
            mg_id = str(mapping.get("muscle_group_id", "")).strip()
            if not mg_id:
                continue
            role = _normalize_muscle_role(str(mapping.get("role") or MUSCLE_ROLE_PRIMARY))
            weight_factor = float(mapping.get("weight_factor", 0.0))

            # Clamp to [0, 1]
            if weight_factor < 0:
                weight_factor = 0.0
            elif weight_factor > 1:
                weight_factor = 1.0

            # Duplicate check
            if mg_id in seen_ids:
                raise ValueError(f"muscle_group_duplicate:{mg_id}")
            seen_ids.add(mg_id)

            validated_rows.append((mg_id, role, round(weight_factor, 4)))

        if not validated_rows:
            raise ValueError("muscle_group_mapping_empty")

        # --- Normalize so sum == 1.0 (with rounding compensation) ---
        total = sum(f for _, _, f in validated_rows)
        if abs(total - 1.0) > _MUSCLE_WEIGHT_TOLERANCE:
            raise ValueError("muscle_group_weights_sum")

        # Distribute any rounding remainder to the last entry so sum is exactly 1.0
        normalized_factors: list[float] = [f for _, _, f in validated_rows]
        current_sum = round(sum(normalized_factors), 4)
        diff = round(1.0 - current_sum, 4)
        if abs(diff) > 0:
            last_idx = len(normalized_factors) - 1
            normalized_factors[last_idx] = round(normalized_factors[last_idx] + diff, 4)

        now = _isoformat(datetime.now(timezone.utc))
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM exercise_muscle_groups WHERE exercise_id = ?",
                (exercise_id,),
            )
            for idx, (mg_id, role, _) in enumerate(validated_rows):
                conn.execute(
                    """
                    INSERT INTO exercise_muscle_groups(
                        exercise_id, muscle_group_id, role, weight_factor,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (exercise_id, mg_id, role, normalized_factors[idx], now, now),
                )
            conn.commit()

    def _get_muscle_group_statistics(
        self, user_id: str | None, household_user_ids: list[str] | None
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self._seed_default_muscle_groups(conn)
            global_stats = self._weighted_muscle_group_aggregates(conn, None)
            personal_stats = (
                self._weighted_muscle_group_aggregates(conn, [user_id]) if user_id else {}
            )
            resolved_household_user_ids = self._resolve_household_user_ids(
                conn, household_user_ids
            )
            household_stats = self._weighted_muscle_group_aggregates(
                conn, resolved_household_user_ids
            )

            rows = conn.execute(
                """
                SELECT
                    id, name_en, name_de, description, icon, body_region,
                    enabled, sort_order, created_at, updated_at
                FROM muscle_groups
                ORDER BY enabled DESC, sort_order ASC, name_en COLLATE NOCASE ASC, id ASC
                """
            ).fetchall()
            result: list[dict[str, Any]] = []
            for row in rows:
                if row is None:
                    continue
                muscle_group_id = str(row["id"])
                global_row = global_stats.get(muscle_group_id, _empty_weighted_muscle_aggregate())
                personal_row = personal_stats.get(muscle_group_id, _empty_weighted_muscle_aggregate())
                household_row = household_stats.get(muscle_group_id, _empty_weighted_muscle_aggregate())
                result.append(
                    {
                        "muscle_group_id": muscle_group_id,
                        "name_en": row["name_en"],
                        "name_de": row["name_de"],
                        "description": row["description"],
                        "icon": row["icon"],
                        "body_region": row["body_region"],
                        "enabled": int(row["enabled"]) == 1,
                        "sort_order": int(row["sort_order"]),
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "total_volume": float(global_row["total_volume"]),
                        "total_sets": int(global_row["total_sets"]),
                        "last_used": global_row["last_used"],
                        "top_exercise": global_row["top_exercise"],
                        "personal_volume": float(personal_row["total_volume"]),
                        "personal_sets": int(personal_row["total_sets"]),
                        "personal_last_used": personal_row["last_used"],
                        "personal_top_exercise": personal_row["top_exercise"],
                        "household_volume": float(household_row["total_volume"]),
                        "household_sets": int(household_row["total_sets"]),
                        "household_last_used": household_row["last_used"],
                        "household_top_exercise": household_row["top_exercise"],
                    }
                )
            return result

    def _get_weekly_summary(
        self,
        start_utc: str,
        end_utc: str,
        user_id: str | None,
        user_ids: list[str] | None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            set_scope_sql, set_scope_params = _scope_filter_sql(
                user_id, user_ids, "sl.user_id"
            )
            set_row = conn.execute(
                f"""
                SELECT
                    COALESCE(SUM(sl.volume), 0) AS total_volume,
                    COUNT(sl.id) AS total_sets,
                    COUNT(DISTINCT DATE(sl.created_at)) AS active_days,
                    MAX(sl.created_at) AS last_set_at
                FROM set_logs sl
                WHERE sl.created_at >= ?
                  AND sl.created_at < ?
                  {set_scope_sql}
                """,
                (start_utc, end_utc, *set_scope_params),
            ).fetchone()

            workout_scope_sql, workout_scope_params = _scope_filter_sql(
                user_id, user_ids, "w.user_id"
            )
            workout_row = conn.execute(
                f"""
                SELECT
                    COUNT(*) AS workout_count,
                    MAX(COALESCE(w.ended_at, w.finished_at, w.started_at)) AS last_workout_at
                FROM workouts w
                WHERE w.started_at >= ?
                  AND w.started_at < ?
                  {workout_scope_sql}
                """,
                (start_utc, end_utc, *workout_scope_params),
            ).fetchone()

            return {
                "total_volume": float(set_row["total_volume"] if set_row is not None else 0.0),
                "total_sets": int(set_row["total_sets"] if set_row is not None else 0),
                "active_days": int(set_row["active_days"] if set_row is not None else 0),
                "last_set_at": set_row["last_set_at"] if set_row is not None else None,
                "workout_count": int(
                    workout_row["workout_count"] if workout_row is not None else 0
                ),
                "last_workout_at": (
                    workout_row["last_workout_at"] if workout_row is not None else None
                ),
            }

    def _get_weekly_exercise_statistics(
        self,
        start_utc: str,
        end_utc: str,
        user_id: str | None,
        user_ids: list[str] | None,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            scope_sql, scope_params = _scope_filter_sql(user_id, user_ids, "sl.user_id")
            rows = conn.execute(
                f"""
                SELECT
                    sl.exercise_id AS exercise_id,
                    ex.name_en AS name_en,
                    ex.name_de AS name_de,
                    COALESCE(SUM(sl.volume), 0) AS volume,
                    COUNT(sl.id) AS sets,
                    COALESCE(MAX(sl.weight), 0) AS max_weight,
                    COALESCE(AVG(sl.weight), 0) AS avg_weight,
                    COALESCE(AVG(sl.reps), 0) AS avg_reps,
                    MAX(sl.created_at) AS last_used_at
                FROM set_logs sl
                LEFT JOIN exercises ex ON ex.id = sl.exercise_id
                WHERE sl.created_at >= ?
                  AND sl.created_at < ?
                  AND sl.exercise_id IS NOT NULL
                  AND TRIM(sl.exercise_id) != ''
                  {scope_sql}
                GROUP BY sl.exercise_id, ex.name_en, ex.name_de
                ORDER BY volume DESC, sets DESC, sl.exercise_id ASC
                """,
                (start_utc, end_utc, *scope_params),
            ).fetchall()

            result: list[dict[str, Any]] = []
            for row in rows:
                if row is None or row["exercise_id"] is None:
                    continue
                exercise_id = str(row["exercise_id"])
                equipment_rows = conn.execute(
                    f"""
                    SELECT DISTINCT
                        sl.equipment_id AS equipment_id,
                        eq.name AS equipment_name,
                        eq.name_en AS equipment_name_en,
                        eq.name_de AS equipment_name_de
                    FROM set_logs sl
                    LEFT JOIN equipment eq ON eq.id = sl.equipment_id
                    WHERE sl.created_at >= ?
                      AND sl.created_at < ?
                      AND sl.exercise_id = ?
                      AND sl.equipment_id IS NOT NULL
                      AND TRIM(sl.equipment_id) != ''
                      {scope_sql}
                    ORDER BY sl.equipment_id ASC
                    """,
                    (start_utc, end_utc, exercise_id, *scope_params),
                ).fetchall()
                equipment_ids = [
                    str(item["equipment_id"])
                    for item in equipment_rows
                    if item is not None and item["equipment_id"] is not None
                ]
                equipment_names = [
                    str(
                        item["equipment_name_de"]
                        or item["equipment_name_en"]
                        or item["equipment_name"]
                        or item["equipment_id"]
                    )
                    for item in equipment_rows
                    if item is not None and item["equipment_id"] is not None
                ]
                result.append(
                    {
                        "exercise_id": exercise_id,
                        "name_en": row["name_en"],
                        "name_de": row["name_de"],
                        "volume": float(row["volume"]),
                        "sets": int(row["sets"]),
                        "max_weight": float(row["max_weight"]),
                        "avg_weight": float(row["avg_weight"]),
                        "avg_reps": float(row["avg_reps"]),
                        "last_used_at": row["last_used_at"],
                        "equipment_ids": equipment_ids,
                        "equipment_names": equipment_names,
                    }
                )
            return result

    def _get_weekly_muscle_group_statistics(
        self,
        start_utc: str,
        end_utc: str,
        user_id: str | None,
        user_ids: list[str] | None,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            scope_sql, scope_params = _scope_filter_sql(user_id, user_ids, "sl.user_id")
            rows = conn.execute(
                f"""
                SELECT
                    emg.muscle_group_id AS muscle_group_id,
                    mg.name_en AS name_en,
                    mg.name_de AS name_de,
                    mg.body_region AS body_region,
                    COALESCE(SUM(sl.volume * emg.weight_factor), 0) AS volume,
                    COUNT(sl.id) AS sets,
                    MAX(sl.created_at) AS last_used_at
                FROM exercise_muscle_groups emg
                JOIN muscle_groups mg ON mg.id = emg.muscle_group_id
                JOIN set_logs sl ON sl.exercise_id = emg.exercise_id
                WHERE sl.created_at >= ?
                  AND sl.created_at < ?
                  {scope_sql}
                GROUP BY emg.muscle_group_id, mg.name_en, mg.name_de, mg.body_region
                ORDER BY volume DESC, sets DESC, emg.muscle_group_id ASC
                """,
                (start_utc, end_utc, *scope_params),
            ).fetchall()

            result: list[dict[str, Any]] = []
            for row in rows:
                if row is None or row["muscle_group_id"] is None:
                    continue
                muscle_group_id = str(row["muscle_group_id"])
                top_row = conn.execute(
                    f"""
                    SELECT
                        sl.exercise_id AS exercise_id,
                        ex.name_en AS name_en,
                        ex.name_de AS name_de,
                        COALESCE(SUM(sl.volume * emg.weight_factor), 0) AS weighted_volume
                    FROM exercise_muscle_groups emg
                    JOIN set_logs sl ON sl.exercise_id = emg.exercise_id
                    LEFT JOIN exercises ex ON ex.id = sl.exercise_id
                    WHERE emg.muscle_group_id = ?
                      AND sl.created_at >= ?
                      AND sl.created_at < ?
                      {scope_sql}
                    GROUP BY sl.exercise_id, ex.name_en, ex.name_de
                    HAVING COALESCE(SUM(sl.volume * emg.weight_factor), 0) > 0
                    ORDER BY weighted_volume DESC, sl.exercise_id ASC
                    LIMIT 1
                    """,
                    (muscle_group_id, start_utc, end_utc, *scope_params),
                ).fetchone()
                result.append(
                    {
                        "muscle_group_id": muscle_group_id,
                        "name_en": row["name_en"],
                        "name_de": row["name_de"],
                        "body_region": row["body_region"],
                        "volume": float(row["volume"]),
                        "sets": int(row["sets"]),
                        "last_used_at": row["last_used_at"],
                        "top_exercise_id": (
                            str(top_row["exercise_id"])
                            if top_row is not None and top_row["exercise_id"] is not None
                            else None
                        ),
                        "top_exercise_name_en": (
                            top_row["name_en"] if top_row is not None else None
                        ),
                        "top_exercise_name_de": (
                            top_row["name_de"] if top_row is not None else None
                        ),
                    }
                )
            return result

    def _get_weekly_user_statistics(
        self, start_utc: str, end_utc: str, user_ids: list[str] | None
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            scope_sql, scope_params = _scope_filter_sql(None, user_ids, "sl.user_id")
            rows = conn.execute(
                f"""
                SELECT
                    sl.user_id AS user_id,
                    u.display_name AS display_name,
                    COALESCE(SUM(sl.volume), 0) AS volume,
                    COUNT(sl.id) AS sets,
                    COUNT(DISTINCT sl.workout_id) AS workout_count,
                    MAX(sl.created_at) AS last_set_at
                FROM set_logs sl
                LEFT JOIN users u ON u.id = sl.user_id
                WHERE sl.created_at >= ?
                  AND sl.created_at < ?
                  {scope_sql}
                GROUP BY sl.user_id, u.display_name
                ORDER BY volume DESC, sets DESC, sl.user_id ASC
                """,
                (start_utc, end_utc, *scope_params),
            ).fetchall()
            result: list[dict[str, Any]] = []
            for row in rows:
                if row is None or row["user_id"] is None:
                    continue
                result.append(
                    {
                        "user_id": str(row["user_id"]),
                        "display_name": row["display_name"],
                        "volume": float(row["volume"]),
                        "sets": int(row["sets"]),
                        "workout_count": int(row["workout_count"]),
                        "last_set_at": row["last_set_at"],
                    }
                )
            return result

    def _get_weekly_volume_history(
        self,
        week_ranges: list[dict[str, Any]],
        user_id: str | None,
        user_ids: list[str] | None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for week_range in week_ranges:
            week_start_utc = str(week_range.get("week_start_utc") or "")
            week_end_utc = str(week_range.get("week_end_utc") or "")
            if not week_start_utc or not week_end_utc:
                continue

            summary = self._get_weekly_summary(week_start_utc, week_end_utc, user_id, user_ids)
            exercise_rows = self._get_weekly_exercise_statistics(
                week_start_utc, week_end_utc, user_id, user_ids
            )
            muscle_rows = self._get_weekly_muscle_group_statistics(
                week_start_utc, week_end_utc, user_id, user_ids
            )

            push_volume = 0.0
            pull_volume = 0.0
            legs_volume = 0.0
            core_volume = 0.0
            for muscle_row in muscle_rows:
                muscle_group_id = str(muscle_row.get("muscle_group_id") or "")
                weighted_volume = float(muscle_row.get("volume", 0.0))
                if muscle_group_id in _WEEKLY_HISTORY_PUSH_IDS:
                    push_volume += weighted_volume
                elif muscle_group_id in _WEEKLY_HISTORY_PULL_IDS:
                    pull_volume += weighted_volume
                elif muscle_group_id in _WEEKLY_HISTORY_LEGS_IDS:
                    legs_volume += weighted_volume
                elif muscle_group_id in _WEEKLY_HISTORY_CORE_IDS:
                    core_volume += weighted_volume

            categorized_volume_total = push_volume + pull_volume + legs_volume + core_volume
            upper_body_volume = push_volume + pull_volume
            lower_body_volume = legs_volume

            if categorized_volume_total > 0:
                push_percent = (push_volume / categorized_volume_total) * 100.0
                pull_percent = (pull_volume / categorized_volume_total) * 100.0
                legs_percent = (legs_volume / categorized_volume_total) * 100.0
                core_percent = (core_volume / categorized_volume_total) * 100.0
                upper_body_percent = (upper_body_volume / categorized_volume_total) * 100.0
                lower_body_percent = (lower_body_volume / categorized_volume_total) * 100.0
            else:
                push_percent = 0.0
                pull_percent = 0.0
                legs_percent = 0.0
                core_percent = 0.0
                upper_body_percent = 0.0
                lower_body_percent = 0.0

            top_exercise = exercise_rows[0] if exercise_rows else None
            top_muscle = muscle_rows[0] if muscle_rows else None
            rows.append(
                {
                    "week_start": week_range.get("week_start_local"),
                    "week_end": week_range.get("week_end_local"),
                    "week_label": week_range.get("week_label"),
                    "iso_year": int(week_range.get("iso_year", 0) or 0),
                    "iso_week": int(week_range.get("iso_week", 0) or 0),
                    "total_volume": float(summary.get("total_volume", 0.0)),
                    "categorized_volume_total": float(categorized_volume_total),
                    "push_volume": float(push_volume),
                    "pull_volume": float(pull_volume),
                    "legs_volume": float(legs_volume),
                    "core_volume": float(core_volume),
                    "upper_body_volume": float(upper_body_volume),
                    "lower_body_volume": float(lower_body_volume),
                    "push_percent": float(push_percent),
                    "pull_percent": float(pull_percent),
                    "legs_percent": float(legs_percent),
                    "core_percent": float(core_percent),
                    "upper_body_percent": float(upper_body_percent),
                    "lower_body_percent": float(lower_body_percent),
                    "total_sets": int(summary.get("total_sets", 0)),
                    "workout_count": int(summary.get("workout_count", 0)),
                    "active_days": int(summary.get("active_days", 0)),
                    "top_exercise_id": (
                        str(top_exercise.get("exercise_id"))
                        if top_exercise is not None and top_exercise.get("exercise_id")
                        else None
                    ),
                    "top_exercise_name_en": (
                        top_exercise.get("name_en") if top_exercise is not None else None
                    ),
                    "top_exercise_name_de": (
                        top_exercise.get("name_de") if top_exercise is not None else None
                    ),
                    "top_exercise_volume": float(
                        top_exercise.get("volume", 0.0) if top_exercise is not None else 0.0
                    ),
                    "top_muscle_group_id": (
                        str(top_muscle.get("muscle_group_id"))
                        if top_muscle is not None and top_muscle.get("muscle_group_id")
                        else None
                    ),
                    "top_muscle_group_name_en": (
                        top_muscle.get("name_en") if top_muscle is not None else None
                    ),
                    "top_muscle_group_name_de": (
                        top_muscle.get("name_de") if top_muscle is not None else None
                    ),
                    "top_muscle_group_volume": float(
                        top_muscle.get("volume", 0.0) if top_muscle is not None else 0.0
                    ),
                }
            )
        return rows

    def _get_weekly_metric_history(
        self,
        week_ranges: list[dict[str, Any]],
        user_id: str | None,
        user_ids: list[str] | None,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        if not week_ranges:
            return result

        with self._connect() as conn:
            scope_sql, scope_params = _scope_filter_sql(user_id, user_ids, "sl.user_id")
            for week_range in week_ranges:
                week_start_utc = str(week_range.get("week_start_utc") or "")
                week_end_utc = str(week_range.get("week_end_utc") or "")
                if not week_start_utc or not week_end_utc:
                    continue

                timezone_name = str(week_range.get("timezone") or "UTC")
                try:
                    local_tz = ZoneInfo(timezone_name)
                except Exception:
                    local_tz = ZoneInfo("UTC")

                rows = conn.execute(
                    f"""
                    SELECT
                        sl.id,
                        sl.workout_id,
                        sl.exercise_id,
                        COALESCE(sl.metric_type, '{DEFAULT_METRIC_TYPE}') AS metric_type,
                        sl.volume,
                        sl.reps,
                        sl.duration_seconds,
                        sl.distance_m,
                        sl.calories,
                        sl.steps,
                        sl.avg_heart_rate,
                        sl.max_heart_rate,
                        sl.load_score,
                        sl.created_at,
                        ex.name_en AS exercise_name_en,
                        ex.name_de AS exercise_name_de
                    FROM set_logs sl
                    LEFT JOIN exercises ex ON ex.id = sl.exercise_id
                    WHERE sl.created_at >= ?
                      AND sl.created_at < ?
                      {scope_sql}
                    ORDER BY sl.created_at ASC, sl.id ASC
                    """,
                    (week_start_utc, week_end_utc, *scope_params),
                ).fetchall()

                entry_count = 0
                workout_ids: set[int] = set()
                active_days: set[str] = set()

                strength_volume_kg = 0.0
                strength_sets = 0
                strength_exercises: set[str] = set()
                strength_scores: dict[str, dict[str, Any]] = {}

                bodyweight_reps = 0
                bodyweight_entries = 0
                bodyweight_load_score = 0.0
                bodyweight_best_reps = 0
                bodyweight_scores: dict[str, dict[str, Any]] = {}

                duration_minutes = 0.0
                duration_entries = 0
                duration_load_score = 0.0
                duration_best_minutes = 0.0
                duration_scores: dict[str, dict[str, Any]] = {}

                hold_minutes = 0.0
                hold_entries = 0
                hold_load_score = 0.0
                hold_best_minutes = 0.0
                hold_scores: dict[str, dict[str, Any]] = {}

                distance_km = 0.0
                distance_minutes = 0.0
                distance_entries = 0
                distance_load_score = 0.0
                distance_best_km = 0.0
                distance_best_pace_min_per_km = 0.0
                distance_best_pace_value: float | None = None
                distance_scores: dict[str, dict[str, Any]] = {}

                cardio_minutes = 0.0
                cardio_km = 0.0
                cardio_calories = 0.0
                cardio_steps = 0
                cardio_entries = 0
                cardio_load_score = 0.0
                cardio_max_heart_rate = 0.0
                cardio_best_km = 0.0
                cardio_best_duration_minutes = 0.0
                cardio_best_pace_min_per_km = 0.0
                cardio_best_pace_value: float | None = None
                cardio_scores: dict[str, dict[str, Any]] = {}
                cardio_hr_weighted_sum = 0.0
                cardio_hr_weighted_duration = 0.0
                cardio_hr_simple_sum = 0.0
                cardio_hr_simple_count = 0

                custom_entries = 0
                custom_minutes = 0.0
                custom_km = 0.0
                custom_load_score = 0.0

                total_minutes = 0.0
                total_distance_km = 0.0
                total_calories = 0.0
                total_steps = 0
                total_reps = 0
                total_strength_volume_kg = 0.0
                total_activity_load_score = 0.0
                total_load_score = 0.0

                def _to_float(value: Any) -> float:
                    if value is None:
                        return 0.0
                    try:
                        return float(value)
                    except (TypeError, ValueError):
                        return 0.0

                def _to_int(value: Any) -> int:
                    if value is None:
                        return 0
                    try:
                        return int(value)
                    except (TypeError, ValueError):
                        return 0

                def _update_top(
                    target: dict[str, dict[str, Any]],
                    exercise_id: str,
                    exercise_name_en: str | None,
                    exercise_name_de: str | None,
                    add_score: float,
                ) -> None:
                    if not exercise_id:
                        return
                    current = target.get(exercise_id)
                    if current is None:
                        target[exercise_id] = {
                            "score": float(add_score),
                            "name_en": exercise_name_en,
                            "name_de": exercise_name_de,
                        }
                        return
                    current["score"] = float(current.get("score", 0.0)) + float(add_score)
                    if current.get("name_en") is None and exercise_name_en is not None:
                        current["name_en"] = exercise_name_en
                    if current.get("name_de") is None and exercise_name_de is not None:
                        current["name_de"] = exercise_name_de

                for row in rows:
                    if row is None:
                        continue
                    entry_count += 1
                    exercise_id = str(row["exercise_id"] or "")
                    metric_type = _normalize_metric_type(row["metric_type"])
                    volume = _to_float(row["volume"])
                    reps = _to_int(row["reps"])
                    duration_seconds = _to_int(row["duration_seconds"])
                    distance_m = _to_float(row["distance_m"])
                    calories = _to_float(row["calories"])
                    steps = _to_int(row["steps"])
                    avg_heart_rate = _to_float(row["avg_heart_rate"])
                    max_heart_rate = _to_float(row["max_heart_rate"])
                    load_score = _to_float(row["load_score"])
                    exercise_name_en = row["exercise_name_en"]
                    exercise_name_de = row["exercise_name_de"]

                    total_reps += max(0, reps)
                    total_load_score += load_score
                    if metric_type != METRIC_TYPE_STRENGTH:
                        total_activity_load_score += load_score

                    workout_id = row["workout_id"]
                    if workout_id is not None:
                        workout_ids.add(int(workout_id))

                    created_at = _parse_iso_datetime(row["created_at"])
                    if created_at is not None:
                        active_days.add(created_at.astimezone(local_tz).date().isoformat())

                    if metric_type == METRIC_TYPE_STRENGTH:
                        strength_volume_kg += volume
                        strength_sets += 1
                        total_strength_volume_kg += volume
                        if exercise_id:
                            strength_exercises.add(exercise_id)
                        _update_top(
                            strength_scores,
                            exercise_id,
                            exercise_name_en,
                            exercise_name_de,
                            volume,
                        )
                        continue

                    if metric_type == METRIC_TYPE_BODYWEIGHT:
                        bodyweight_reps += max(0, reps)
                        bodyweight_entries += 1
                        bodyweight_load_score += load_score
                        bodyweight_best_reps = max(bodyweight_best_reps, reps)
                        top_score = load_score if load_score > 0 else float(max(0, reps))
                        _update_top(
                            bodyweight_scores,
                            exercise_id,
                            exercise_name_en,
                            exercise_name_de,
                            top_score,
                        )
                        continue

                    if metric_type == METRIC_TYPE_DURATION:
                        duration_value = max(0.0, float(duration_seconds) / 60.0)
                        duration_minutes += duration_value
                        duration_entries += 1
                        duration_load_score += load_score
                        total_minutes += duration_value
                        duration_best_minutes = max(duration_best_minutes, duration_value)
                        _update_top(
                            duration_scores,
                            exercise_id,
                            exercise_name_en,
                            exercise_name_de,
                            duration_value,
                        )
                        continue

                    if metric_type == METRIC_TYPE_HOLD:
                        hold_value = max(0.0, float(duration_seconds) / 60.0)
                        hold_minutes += hold_value
                        hold_entries += 1
                        hold_load_score += load_score
                        total_minutes += hold_value
                        hold_best_minutes = max(hold_best_minutes, hold_value)
                        _update_top(
                            hold_scores,
                            exercise_id,
                            exercise_name_en,
                            exercise_name_de,
                            hold_value,
                        )
                        continue

                    if metric_type == METRIC_TYPE_DISTANCE:
                        distance_value = max(0.0, float(distance_m) / 1000.0)
                        duration_value = max(0.0, float(duration_seconds) / 60.0)
                        distance_km += distance_value
                        distance_minutes += duration_value
                        distance_entries += 1
                        distance_load_score += load_score
                        total_distance_km += distance_value
                        total_minutes += duration_value
                        distance_best_km = max(distance_best_km, distance_value)
                        _update_top(
                            distance_scores,
                            exercise_id,
                            exercise_name_en,
                            exercise_name_de,
                            distance_value,
                        )
                        if duration_seconds > 0 and distance_m > 0:
                            pace = (float(duration_seconds) / 60.0) / (
                                float(distance_m) / 1000.0
                            )
                            if distance_best_pace_value is None or pace < distance_best_pace_value:
                                distance_best_pace_value = pace
                        continue

                    if metric_type == METRIC_TYPE_CARDIO:
                        cardio_duration = max(0.0, float(duration_seconds) / 60.0)
                        cardio_distance = max(0.0, float(distance_m) / 1000.0)
                        cardio_minutes += cardio_duration
                        cardio_km += cardio_distance
                        cardio_calories += max(0.0, calories)
                        cardio_steps += max(0, steps)
                        cardio_entries += 1
                        cardio_load_score += load_score
                        total_minutes += cardio_duration
                        total_distance_km += cardio_distance
                        total_calories += max(0.0, calories)
                        total_steps += max(0, steps)
                        cardio_best_km = max(cardio_best_km, cardio_distance)
                        cardio_best_duration_minutes = max(
                            cardio_best_duration_minutes, cardio_duration
                        )
                        if max_heart_rate > cardio_max_heart_rate:
                            cardio_max_heart_rate = max_heart_rate
                        if avg_heart_rate > 0:
                            if duration_seconds > 0:
                                cardio_hr_weighted_sum += avg_heart_rate * float(duration_seconds)
                                cardio_hr_weighted_duration += float(duration_seconds)
                            else:
                                cardio_hr_simple_sum += avg_heart_rate
                                cardio_hr_simple_count += 1
                        if duration_seconds > 0 and distance_m > 0:
                            pace = (float(duration_seconds) / 60.0) / (
                                float(distance_m) / 1000.0
                            )
                            if cardio_best_pace_value is None or pace < cardio_best_pace_value:
                                cardio_best_pace_value = pace
                        cardio_top_score = (
                            load_score
                            if load_score > 0
                            else (float(duration_seconds) if duration_seconds > 0 else distance_m)
                        )
                        _update_top(
                            cardio_scores,
                            exercise_id,
                            exercise_name_en,
                            exercise_name_de,
                            cardio_top_score,
                        )
                        continue

                    custom_entries += 1
                    custom_minutes_value = max(0.0, float(duration_seconds) / 60.0)
                    custom_distance_value = max(0.0, float(distance_m) / 1000.0)
                    custom_minutes += custom_minutes_value
                    custom_km += custom_distance_value
                    custom_load_score += load_score
                    total_minutes += custom_minutes_value
                    total_distance_km += custom_distance_value

                def _top_payload(source: dict[str, dict[str, Any]]) -> tuple[str | None, str | None, str | None, float]:
                    if not source:
                        return None, None, None, 0.0
                    exercise_id, data = max(
                        source.items(),
                        key=lambda item: (
                            float(item[1].get("score", 0.0)),
                            item[0],
                        ),
                    )
                    return (
                        exercise_id,
                        data.get("name_en"),
                        data.get("name_de"),
                        float(data.get("score", 0.0)),
                    )

                strength_top_id, strength_top_en, strength_top_de, strength_top_volume = _top_payload(
                    strength_scores
                )
                bodyweight_top_id, bodyweight_top_en, bodyweight_top_de, _ = _top_payload(
                    bodyweight_scores
                )
                duration_top_id, duration_top_en, duration_top_de, _ = _top_payload(
                    duration_scores
                )
                hold_top_id, hold_top_en, hold_top_de, _ = _top_payload(hold_scores)
                distance_top_id, distance_top_en, distance_top_de, _ = _top_payload(
                    distance_scores
                )
                cardio_top_id, cardio_top_en, cardio_top_de, _ = _top_payload(cardio_scores)

                if cardio_hr_weighted_duration > 0:
                    cardio_avg_heart_rate = cardio_hr_weighted_sum / cardio_hr_weighted_duration
                elif cardio_hr_simple_count > 0:
                    cardio_avg_heart_rate = cardio_hr_simple_sum / float(cardio_hr_simple_count)
                else:
                    cardio_avg_heart_rate = 0.0

                distance_best_pace_min_per_km = (
                    float(distance_best_pace_value)
                    if distance_best_pace_value is not None
                    else 0.0
                )
                cardio_best_pace_min_per_km = (
                    float(cardio_best_pace_value) if cardio_best_pace_value is not None else 0.0
                )

                result.append(
                    {
                        "week_start": week_range.get("week_start_local"),
                        "week_end": week_range.get("week_end_local"),
                        "week_label": week_range.get("week_label"),
                        "iso_year": int(week_range.get("iso_year", 0) or 0),
                        "iso_week": int(week_range.get("iso_week", 0) or 0),
                        "entry_count": int(entry_count),
                        "workout_count": len(workout_ids),
                        "active_days": len(active_days),
                        "total_load_score": round(total_load_score, 1),
                        "strength_volume_kg": round(strength_volume_kg, 1),
                        "strength_sets": int(strength_sets),
                        "strength_exercise_count": len(strength_exercises),
                        "strength_top_exercise_id": strength_top_id,
                        "strength_top_exercise_name_en": strength_top_en,
                        "strength_top_exercise_name_de": strength_top_de,
                        "strength_top_volume_kg": round(strength_top_volume, 1),
                        "bodyweight_reps": int(bodyweight_reps),
                        "bodyweight_entries": int(bodyweight_entries),
                        "bodyweight_load_score": round(bodyweight_load_score, 1),
                        "bodyweight_top_exercise_id": bodyweight_top_id,
                        "bodyweight_top_exercise_name_en": bodyweight_top_en,
                        "bodyweight_top_exercise_name_de": bodyweight_top_de,
                        "bodyweight_best_reps": int(bodyweight_best_reps),
                        "duration_minutes": round(duration_minutes, 1),
                        "duration_entries": int(duration_entries),
                        "duration_load_score": round(duration_load_score, 1),
                        "duration_top_exercise_id": duration_top_id,
                        "duration_top_exercise_name_en": duration_top_en,
                        "duration_top_exercise_name_de": duration_top_de,
                        "duration_best_minutes": round(duration_best_minutes, 1),
                        "hold_minutes": round(hold_minutes, 1),
                        "hold_entries": int(hold_entries),
                        "hold_load_score": round(hold_load_score, 1),
                        "hold_top_exercise_id": hold_top_id,
                        "hold_top_exercise_name_en": hold_top_en,
                        "hold_top_exercise_name_de": hold_top_de,
                        "hold_best_minutes": round(hold_best_minutes, 1),
                        "distance_km": round(distance_km, 2),
                        "distance_minutes": round(distance_minutes, 1),
                        "distance_entries": int(distance_entries),
                        "distance_load_score": round(distance_load_score, 1),
                        "distance_best_km": round(distance_best_km, 2),
                        "distance_best_pace_min_per_km": round(
                            distance_best_pace_min_per_km, 2
                        ),
                        "distance_top_exercise_id": distance_top_id,
                        "distance_top_exercise_name_en": distance_top_en,
                        "distance_top_exercise_name_de": distance_top_de,
                        "cardio_minutes": round(cardio_minutes, 1),
                        "cardio_km": round(cardio_km, 2),
                        "cardio_calories": round(cardio_calories, 1),
                        "cardio_steps": int(cardio_steps),
                        "cardio_entries": int(cardio_entries),
                        "cardio_load_score": round(cardio_load_score, 1),
                        "cardio_avg_heart_rate": round(cardio_avg_heart_rate, 1),
                        "cardio_max_heart_rate": round(cardio_max_heart_rate, 1),
                        "cardio_best_km": round(cardio_best_km, 2),
                        "cardio_best_duration_minutes": round(
                            cardio_best_duration_minutes, 1
                        ),
                        "cardio_best_pace_min_per_km": round(cardio_best_pace_min_per_km, 2),
                        "cardio_top_exercise_id": cardio_top_id,
                        "cardio_top_exercise_name_en": cardio_top_en,
                        "cardio_top_exercise_name_de": cardio_top_de,
                        "custom_entries": int(custom_entries),
                        "custom_minutes": round(custom_minutes, 1),
                        "custom_km": round(custom_km, 2),
                        "custom_load_score": round(custom_load_score, 1),
                        "total_minutes": round(total_minutes, 1),
                        "total_distance_km": round(total_distance_km, 2),
                        "total_calories": round(total_calories, 1),
                        "total_steps": int(total_steps),
                        "total_reps": int(total_reps),
                        "total_entries": int(entry_count),
                        "total_strength_volume_kg": round(total_strength_volume_kg, 1),
                        "total_activity_load_score": round(total_activity_load_score, 1),
                    }
                )
        return result

    def _get_core_total_statistics(
        self,
        user_id: str | None,
        user_ids: list[str] | None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            scope_sql, scope_params = _scope_filter_sql(user_id, user_ids, "sl.user_id")
            row = conn.execute(
                f"""
                SELECT
                    COALESCE(
                        SUM(
                            CASE
                                WHEN COALESCE(sl.metric_type, '{DEFAULT_METRIC_TYPE}') = '{METRIC_TYPE_STRENGTH}'
                                    THEN COALESCE(sl.volume, 0)
                                ELSE 0
                            END
                        ),
                        0
                    ) AS total_strength_volume,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN COALESCE(sl.metric_type, '{DEFAULT_METRIC_TYPE}') != '{METRIC_TYPE_STRENGTH}'
                                    THEN COALESCE(sl.load_score, 0)
                                ELSE 0
                            END
                        ),
                        0
                    ) AS total_activity_load,
                    COALESCE(SUM(COALESCE(sl.duration_seconds, 0)), 0) AS total_duration_seconds,
                    COALESCE(SUM(COALESCE(sl.distance_m, 0)), 0) AS total_distance_m,
                    COALESCE(SUM(COALESCE(sl.reps, 0)), 0) AS total_reps,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN COALESCE(sl.metric_type, '{DEFAULT_METRIC_TYPE}') IN ('{METRIC_TYPE_STRENGTH}', '{METRIC_TYPE_BODYWEIGHT}')
                                    THEN 1
                                ELSE 0
                            END
                        ),
                        0
                    ) AS total_sets,
                    MAX(sl.created_at) AS last_entry_at
                FROM set_logs sl
                WHERE 1 = 1
                  {scope_sql}
                """,
                scope_params,
            ).fetchone()
            if row is None:
                return {
                    "total_strength_volume": 0.0,
                    "total_activity_load": 0.0,
                    "total_duration_seconds": 0,
                    "total_distance_m": 0.0,
                    "total_reps": 0,
                    "total_sets": 0,
                    "last_entry_at": None,
                }
            return {
                "total_strength_volume": float(row["total_strength_volume"] or 0.0),
                "total_activity_load": float(row["total_activity_load"] or 0.0),
                "total_duration_seconds": int(row["total_duration_seconds"] or 0),
                "total_distance_m": float(row["total_distance_m"] or 0.0),
                "total_reps": int(row["total_reps"] or 0),
                "total_sets": int(row["total_sets"] or 0),
                "last_entry_at": row["last_entry_at"],
            }

    def _get_daily_metric_statistics(
        self,
        day_ranges: list[dict[str, Any]],
        user_id: str | None,
        user_ids: list[str] | None,
        include_scope_breakdowns: bool,
        breakdown_limit: int,
    ) -> list[dict[str, Any]]:
        if not day_ranges:
            return []

        safe_breakdown_limit = max(1, min(int(breakdown_limit), 25))
        ordered_ranges = sorted(
            list(day_ranges),
            key=lambda row: str(row.get("day_start_utc") or ""),
        )
        first_start_utc = str(ordered_ranges[0].get("day_start_utc") or "")
        last_end_utc = str(ordered_ranges[-1].get("day_end_utc") or "")
        if not first_start_utc or not last_end_utc:
            return []

        timezone_name = str(ordered_ranges[0].get("timezone") or "UTC")
        try:
            local_tz = ZoneInfo(timezone_name)
        except Exception:
            local_tz = ZoneInfo("UTC")

        day_payload_by_date: dict[str, dict[str, Any]] = {}
        for day_range in ordered_ranges:
            day_key = str(day_range.get("date") or "")
            if not day_key:
                continue
            day_payload_by_date[day_key] = _empty_daily_metric_bucket(day_range)

        if not day_payload_by_date:
            return []

        with self._connect() as conn:
            scope_sql, scope_params = _scope_filter_sql(user_id, user_ids, "sl.user_id")
            rows = conn.execute(
                f"""
                SELECT
                    sl.id,
                    sl.workout_id,
                    sl.exercise_id,
                    sl.equipment_id,
                    COALESCE(sl.metric_type, '{DEFAULT_METRIC_TYPE}') AS metric_type,
                    sl.volume,
                    sl.reps,
                    sl.duration_seconds,
                    sl.distance_m,
                    sl.calories,
                    sl.steps,
                    sl.avg_heart_rate,
                    sl.max_heart_rate,
                    sl.load_score,
                    sl.created_at,
                    ex.name_en AS exercise_name_en,
                    ex.name_de AS exercise_name_de,
                    eq.name AS equipment_name,
                    eq.name_en AS equipment_name_en,
                    eq.name_de AS equipment_name_de
                FROM set_logs sl
                LEFT JOIN exercises ex ON ex.id = sl.exercise_id
                LEFT JOIN equipment eq ON eq.id = sl.equipment_id
                WHERE sl.created_at >= ?
                  AND sl.created_at < ?
                  {scope_sql}
                ORDER BY sl.created_at ASC, sl.id ASC
                """,
                (first_start_utc, last_end_utc, *scope_params),
            ).fetchall()

            # day->scope breakdown maps
            day_exercises: dict[str, dict[str, dict[str, Any]]] = {
                key: {} for key in day_payload_by_date
            }
            day_equipment: dict[str, dict[str, dict[str, Any]]] = {
                key: {} for key in day_payload_by_date
            }
            day_workout_ids: dict[str, set[int]] = {key: set() for key in day_payload_by_date}

            def _to_float(value: Any) -> float:
                try:
                    return float(value or 0.0)
                except (TypeError, ValueError):
                    return 0.0

            def _to_int(value: Any) -> int:
                try:
                    return int(value or 0)
                except (TypeError, ValueError):
                    return 0

            def _exercise_name(row: sqlite3.Row) -> str:
                return str(
                    row["exercise_name_de"]
                    or row["exercise_name_en"]
                    or row["exercise_id"]
                    or "Unknown"
                )

            def _equipment_name(row: sqlite3.Row) -> str:
                return str(
                    row["equipment_name_de"]
                    or row["equipment_name_en"]
                    or row["equipment_name"]
                    or row["equipment_id"]
                    or "Unknown"
                )

            def _day_key_from_created_at(created_at: Any) -> str | None:
                parsed = _parse_iso_datetime(created_at)
                if parsed is None:
                    return None
                return parsed.astimezone(local_tz).date().isoformat()

            for row in rows:
                if row is None:
                    continue
                day_key = _day_key_from_created_at(row["created_at"])
                if day_key is None or day_key not in day_payload_by_date:
                    continue

                metric_type = _normalize_metric_type(row["metric_type"])
                payload = day_payload_by_date[day_key]
                exercise_id = str(row["exercise_id"] or "")
                equipment_id = str(row["equipment_id"] or "")

                volume = _to_float(row["volume"])
                reps = max(0, _to_int(row["reps"]))
                duration_seconds = max(0, _to_int(row["duration_seconds"]))
                distance_m = max(0.0, _to_float(row["distance_m"]))
                calories = max(0.0, _to_float(row["calories"]))
                steps = max(0, _to_int(row["steps"]))
                avg_hr = max(0.0, _to_float(row["avg_heart_rate"]))
                max_hr = max(0.0, _to_float(row["max_heart_rate"]))
                load_score = _to_float(row["load_score"])

                payload["entry_count"] += 1
                payload["active"] = payload["entry_count"] > 0
                payload["total_load_score"] += load_score
                payload["total_minutes"] += float(duration_seconds) / 60.0
                payload["total_distance_km"] += distance_m / 1000.0
                payload["total_calories"] += calories
                payload["total_steps"] += steps
                payload["total_reps"] += reps

                if metric_type == METRIC_TYPE_STRENGTH:
                    payload["strength_volume_kg"] += volume
                    payload["strength_sets"] += 1
                    payload["strength_reps"] += reps
                    payload["total_strength_volume_kg"] += volume
                    payload["total_sets"] += 1
                elif metric_type == METRIC_TYPE_BODYWEIGHT:
                    payload["bodyweight_reps"] += reps
                    payload["bodyweight_entries"] += 1
                    payload["bodyweight_load_score"] += load_score
                    payload["total_activity_load_score"] += load_score
                    payload["total_sets"] += 1
                elif metric_type == METRIC_TYPE_DURATION:
                    minutes = float(duration_seconds) / 60.0
                    payload["duration_minutes"] += minutes
                    payload["duration_entries"] += 1
                    payload["duration_load_score"] += load_score
                    payload["total_activity_load_score"] += load_score
                elif metric_type == METRIC_TYPE_HOLD:
                    minutes = float(duration_seconds) / 60.0
                    payload["hold_minutes"] += minutes
                    payload["hold_entries"] += 1
                    payload["hold_load_score"] += load_score
                    payload["total_activity_load_score"] += load_score
                elif metric_type == METRIC_TYPE_DISTANCE:
                    minutes = float(duration_seconds) / 60.0
                    km = distance_m / 1000.0
                    payload["distance_minutes"] += minutes
                    payload["distance_km"] += km
                    payload["distance_entries"] += 1
                    payload["distance_load_score"] += load_score
                    payload["total_activity_load_score"] += load_score
                elif metric_type == METRIC_TYPE_CARDIO:
                    minutes = float(duration_seconds) / 60.0
                    km = distance_m / 1000.0
                    payload["cardio_minutes"] += minutes
                    payload["cardio_km"] += km
                    payload["cardio_calories"] += calories
                    payload["cardio_steps"] += steps
                    payload["cardio_entries"] += 1
                    payload["cardio_load_score"] += load_score
                    payload["total_activity_load_score"] += load_score
                    payload["_cardio_hr_duration_weighted_sum"] += avg_hr * float(
                        duration_seconds
                    )
                    payload["_cardio_hr_duration_weight"] += float(duration_seconds)
                    if duration_seconds <= 0 and avg_hr > 0:
                        payload["_cardio_hr_simple_sum"] += avg_hr
                        payload["_cardio_hr_simple_count"] += 1
                    payload["cardio_max_heart_rate"] = max(
                        float(payload["cardio_max_heart_rate"]), max_hr
                    )
                else:
                    minutes = float(duration_seconds) / 60.0
                    km = distance_m / 1000.0
                    payload["custom_entries"] += 1
                    payload["custom_minutes"] += minutes
                    payload["custom_km"] += km
                    payload["custom_load_score"] += load_score
                    payload["total_activity_load_score"] += load_score

                workout_id = row["workout_id"]
                if workout_id is not None:
                    day_workout_ids[day_key].add(int(workout_id))

                # Exercise breakdown
                if include_scope_breakdowns and exercise_id:
                    ex_map = day_exercises[day_key]
                    ex_entry = ex_map.get(exercise_id)
                    if ex_entry is None:
                        ex_entry = {
                            "exercise_id": exercise_id,
                            "exercise_name": _exercise_name(row),
                            "metric_type": metric_type,
                            "strength_volume_kg": 0.0,
                            "activity_load_score": 0.0,
                            "duration_minutes": 0.0,
                            "distance_km": 0.0,
                            "reps": 0,
                            "entries": 0,
                            "sets": 0,
                        }
                        ex_map[exercise_id] = ex_entry
                    ex_entry["entries"] += 1
                    ex_entry["reps"] += reps
                    ex_entry["duration_minutes"] += float(duration_seconds) / 60.0
                    ex_entry["distance_km"] += distance_m / 1000.0
                    if metric_type == METRIC_TYPE_STRENGTH:
                        ex_entry["strength_volume_kg"] += volume
                        ex_entry["sets"] += 1
                    elif metric_type == METRIC_TYPE_BODYWEIGHT:
                        ex_entry["sets"] += 1
                        ex_entry["activity_load_score"] += load_score
                    else:
                        ex_entry["activity_load_score"] += load_score

                # Equipment breakdown
                if include_scope_breakdowns and equipment_id:
                    eq_map = day_equipment[day_key]
                    eq_entry = eq_map.get(equipment_id)
                    if eq_entry is None:
                        eq_entry = {
                            "equipment_id": equipment_id,
                            "equipment_name": _equipment_name(row),
                            "strength_volume_kg": 0.0,
                            "activity_load_score": 0.0,
                            "duration_minutes": 0.0,
                            "distance_km": 0.0,
                            "reps": 0,
                            "entries": 0,
                            "sets": 0,
                        }
                        eq_map[equipment_id] = eq_entry
                    eq_entry["entries"] += 1
                    eq_entry["reps"] += reps
                    eq_entry["duration_minutes"] += float(duration_seconds) / 60.0
                    eq_entry["distance_km"] += distance_m / 1000.0
                    if metric_type == METRIC_TYPE_STRENGTH:
                        eq_entry["strength_volume_kg"] += volume
                        eq_entry["sets"] += 1
                    elif metric_type == METRIC_TYPE_BODYWEIGHT:
                        eq_entry["sets"] += 1
                        eq_entry["activity_load_score"] += load_score
                    else:
                        eq_entry["activity_load_score"] += load_score

            # Muscle-group breakdown query (aggregated, no per-row roundtrips)
            muscle_rows = conn.execute(
                f"""
                SELECT
                    DATE(sl.created_at) AS created_date_utc,
                    sl.created_at AS created_at,
                    mg.id AS muscle_group_id,
                    mg.name_en AS muscle_group_name_en,
                    mg.name_de AS muscle_group_name_de,
                    SUM(
                        CASE
                            WHEN COALESCE(sl.metric_type, '{DEFAULT_METRIC_TYPE}') = '{METRIC_TYPE_STRENGTH}'
                                THEN COALESCE(sl.volume, 0) * COALESCE(emg.weight_factor, 1.0)
                            ELSE 0
                        END
                    ) AS strength_value,
                    SUM(
                        CASE
                            WHEN COALESCE(sl.metric_type, '{DEFAULT_METRIC_TYPE}') != '{METRIC_TYPE_STRENGTH}'
                                THEN COALESCE(sl.load_score, 0) * COALESCE(emg.weight_factor, 1.0)
                            ELSE 0
                        END
                    ) AS activity_value,
                    COUNT(sl.id) AS entry_count,
                    SUM(
                        CASE
                            WHEN COALESCE(sl.metric_type, '{DEFAULT_METRIC_TYPE}') = '{METRIC_TYPE_STRENGTH}'
                                THEN COALESCE(sl.volume, 0) * COALESCE(emg.weight_factor, 1.0)
                            ELSE COALESCE(sl.load_score, 0) * COALESCE(emg.weight_factor, 1.0)
                        END
                    ) AS contribution_value
                FROM set_logs sl
                JOIN exercise_muscle_groups emg ON emg.exercise_id = sl.exercise_id
                JOIN muscle_groups mg ON mg.id = emg.muscle_group_id
                WHERE sl.created_at >= ?
                  AND sl.created_at < ?
                  {scope_sql}
                GROUP BY created_date_utc, sl.created_at, mg.id, mg.name_en, mg.name_de
                """,
                (first_start_utc, last_end_utc, *scope_params),
            ).fetchall()

            day_muscles: dict[str, dict[str, dict[str, Any]]] = {
                key: {} for key in day_payload_by_date
            }
            for row in muscle_rows:
                if row is None:
                    continue
                day_key = _day_key_from_created_at(row["created_at"])
                if day_key is None or day_key not in day_payload_by_date:
                    continue
                muscle_group_id = str(row["muscle_group_id"] or "")
                if not muscle_group_id:
                    continue
                mg_map = day_muscles[day_key]
                mg_entry = mg_map.get(muscle_group_id)
                if mg_entry is None:
                    mg_entry = {
                        "muscle_group_id": muscle_group_id,
                        "muscle_group_name": str(
                            row["muscle_group_name_de"]
                            or row["muscle_group_name_en"]
                            or muscle_group_id
                        ),
                        "strength_volume_kg": 0.0,
                        "activity_load_score": 0.0,
                        "duration_minutes": 0.0,
                        "distance_km": 0.0,
                        "reps": 0,
                        "entries": 0,
                        "_value": 0.0,
                    }
                    mg_map[muscle_group_id] = mg_entry
                mg_entry["strength_volume_kg"] += float(row["strength_value"] or 0.0)
                mg_entry["activity_load_score"] += float(row["activity_value"] or 0.0)
                mg_entry["entries"] += int(row["entry_count"] or 0)
                mg_entry["_value"] += float(row["contribution_value"] or 0.0)

            # finalize payload
            for day_key, payload in day_payload_by_date.items():
                payload["workout_count"] = len(day_workout_ids.get(day_key, set()))
                payload["active"] = payload["entry_count"] > 0
                hr_weight = float(payload.pop("_cardio_hr_duration_weight", 0.0))
                hr_weight_sum = float(payload.pop("_cardio_hr_duration_weighted_sum", 0.0))
                hr_simple_sum = float(payload.pop("_cardio_hr_simple_sum", 0.0))
                hr_simple_count = int(payload.pop("_cardio_hr_simple_count", 0))
                if hr_weight > 0:
                    payload["cardio_avg_heart_rate"] = hr_weight_sum / hr_weight
                elif hr_simple_count > 0:
                    payload["cardio_avg_heart_rate"] = hr_simple_sum / float(hr_simple_count)
                else:
                    payload["cardio_avg_heart_rate"] = 0.0

                ex_rows = list(day_exercises.get(day_key, {}).values())
                ex_rows.sort(
                    key=lambda row: (
                        _metric_aggregate_value(row),
                        row.get("entries", 0),
                        str(row.get("exercise_id") or ""),
                    ),
                    reverse=True,
                )
                eq_rows = list(day_equipment.get(day_key, {}).values())
                eq_rows.sort(
                    key=lambda row: (
                        _metric_aggregate_value(row),
                        row.get("entries", 0),
                        str(row.get("equipment_id") or ""),
                    ),
                    reverse=True,
                )
                mg_rows = list(day_muscles.get(day_key, {}).values())
                mg_rows.sort(
                    key=lambda row: (
                        float(row.get("_value") or 0.0),
                        str(row.get("muscle_group_id") or ""),
                    ),
                    reverse=True,
                )

                top_ex = ex_rows[0] if ex_rows else None
                top_eq = eq_rows[0] if eq_rows else None
                top_mg = mg_rows[0] if mg_rows else None

                payload["top_exercise_id"] = top_ex.get("exercise_id") if top_ex else None
                payload["top_exercise_name"] = top_ex.get("exercise_name") if top_ex else None
                payload["top_exercise_metric_type"] = (
                    top_ex.get("metric_type") if top_ex else None
                )
                payload["top_exercise_value"] = (
                    round(_metric_aggregate_value(top_ex), 2) if top_ex else 0.0
                )
                payload["top_equipment_id"] = top_eq.get("equipment_id") if top_eq else None
                payload["top_equipment_name"] = top_eq.get("equipment_name") if top_eq else None
                payload["top_equipment_value"] = (
                    round(_metric_aggregate_value(top_eq), 2) if top_eq else 0.0
                )
                payload["top_muscle_group_id"] = (
                    top_mg.get("muscle_group_id") if top_mg else None
                )
                payload["top_muscle_group_name"] = (
                    top_mg.get("muscle_group_name") if top_mg else None
                )
                payload["top_muscle_group_value"] = (
                    round(float(top_mg.get("_value") or 0.0), 2) if top_mg else 0.0
                )

                if include_scope_breakdowns:
                    payload["exercises"] = [
                        {
                            "exercise_id": str(item.get("exercise_id") or ""),
                            "exercise_name": item.get("exercise_name"),
                            "metric_type": item.get("metric_type"),
                            "strength_volume_kg": round(
                                float(item.get("strength_volume_kg", 0.0)), 2
                            ),
                            "activity_load_score": round(
                                float(item.get("activity_load_score", 0.0)), 2
                            ),
                            "duration_minutes": round(
                                float(item.get("duration_minutes", 0.0)), 2
                            ),
                            "distance_km": round(float(item.get("distance_km", 0.0)), 3),
                            "reps": int(item.get("reps", 0)),
                            "entries": int(item.get("entries", 0)),
                            "sets": int(item.get("sets", 0)),
                        }
                        for item in ex_rows[:safe_breakdown_limit]
                    ]
                    payload["equipment"] = [
                        {
                            "equipment_id": str(item.get("equipment_id") or ""),
                            "equipment_name": item.get("equipment_name"),
                            "strength_volume_kg": round(
                                float(item.get("strength_volume_kg", 0.0)), 2
                            ),
                            "activity_load_score": round(
                                float(item.get("activity_load_score", 0.0)), 2
                            ),
                            "duration_minutes": round(
                                float(item.get("duration_minutes", 0.0)), 2
                            ),
                            "distance_km": round(float(item.get("distance_km", 0.0)), 3),
                            "reps": int(item.get("reps", 0)),
                            "entries": int(item.get("entries", 0)),
                            "sets": int(item.get("sets", 0)),
                        }
                        for item in eq_rows[:safe_breakdown_limit]
                    ]
                    payload["muscle_groups"] = [
                        {
                            "muscle_group_id": str(item.get("muscle_group_id") or ""),
                            "muscle_group_name": item.get("muscle_group_name"),
                            "strength_volume_kg": round(
                                float(item.get("strength_volume_kg", 0.0)), 2
                            ),
                            "activity_load_score": round(
                                float(item.get("activity_load_score", 0.0)), 2
                            ),
                            "duration_minutes": round(
                                float(item.get("duration_minutes", 0.0)), 2
                            ),
                            "distance_km": round(float(item.get("distance_km", 0.0)), 3),
                            "reps": int(item.get("reps", 0)),
                            "entries": int(item.get("entries", 0)),
                            "value": round(float(item.get("_value") or 0.0), 2),
                        }
                        for item in mg_rows[:safe_breakdown_limit]
                    ]
                else:
                    payload["exercises"] = []
                    payload["equipment"] = []
                    payload["muscle_groups"] = []

                # round top-level numeric values
                payload["total_load_score"] = round(float(payload["total_load_score"]), 2)
                payload["total_activity_load_score"] = round(
                    float(payload["total_activity_load_score"]), 2
                )
                payload["total_strength_volume_kg"] = round(
                    float(payload["total_strength_volume_kg"]), 2
                )
                payload["total_minutes"] = round(float(payload["total_minutes"]), 2)
                payload["total_distance_km"] = round(float(payload["total_distance_km"]), 3)
                payload["total_calories"] = round(float(payload["total_calories"]), 2)
                payload["strength_volume_kg"] = round(float(payload["strength_volume_kg"]), 2)
                payload["duration_minutes"] = round(float(payload["duration_minutes"]), 2)
                payload["hold_minutes"] = round(float(payload["hold_minutes"]), 2)
                payload["distance_km"] = round(float(payload["distance_km"]), 3)
                payload["distance_minutes"] = round(float(payload["distance_minutes"]), 2)
                payload["cardio_minutes"] = round(float(payload["cardio_minutes"]), 2)
                payload["cardio_km"] = round(float(payload["cardio_km"]), 3)
                payload["cardio_calories"] = round(float(payload["cardio_calories"]), 2)
                payload["cardio_avg_heart_rate"] = round(
                    float(payload["cardio_avg_heart_rate"]), 2
                )
                payload["cardio_max_heart_rate"] = round(
                    float(payload["cardio_max_heart_rate"]), 2
                )
                payload["custom_minutes"] = round(float(payload["custom_minutes"]), 2)
                payload["custom_km"] = round(float(payload["custom_km"]), 3)

        ordered_dates = [str(row.get("date") or "") for row in ordered_ranges if row.get("date")]
        return [day_payload_by_date[day_key] for day_key in ordered_dates if day_key in day_payload_by_date]

    def _get_household_total_volume(self, user_ids: list[str] | None) -> float:
        with self._connect() as conn:
            resolved = self._resolve_household_user_ids(conn, user_ids)
            if resolved == []:
                return 0.0
            sql, params = _in_clause_sql(
                "SELECT COALESCE(SUM(volume), 0) AS value FROM set_logs",
                "user_id",
                resolved,
            )
            row = conn.execute(sql, params).fetchone()
            return float(row["value"] if row is not None else 0.0)

    def _get_household_set_count(self, user_ids: list[str] | None) -> int:
        with self._connect() as conn:
            resolved = self._resolve_household_user_ids(conn, user_ids)
            if resolved == []:
                return 0
            sql, params = _in_clause_sql(
                "SELECT COUNT(*) AS value FROM set_logs",
                "user_id",
                resolved,
            )
            row = conn.execute(sql, params).fetchone()
            return int(row["value"] if row is not None else 0)

    def _get_household_workout_count(self, user_ids: list[str] | None) -> int:
        with self._connect() as conn:
            resolved = self._resolve_household_user_ids(conn, user_ids)
            if resolved == []:
                return 0
            sql, params = _in_clause_sql(
                "SELECT COUNT(*) AS value FROM workouts",
                "user_id",
                resolved,
            )
            row = conn.execute(sql, params).fetchone()
            return int(row["value"] if row is not None else 0)

    def _get_household_recent_sets(
        self, limit: int, user_ids: list[str] | None
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            resolved = self._resolve_household_user_ids(conn, user_ids)
            if resolved == []:
                return []
            sql, params = _in_clause_sql(
                """
                SELECT
                    id, user_id, workout_id, exercise, exercise_id, equipment_id, metric_type,
                    weight, reps, volume, notes, created_at, updated_at,
                    duration_seconds, distance_m, calories, steps, avg_heart_rate, max_heart_rate,
                    avg_power_watts, max_power_watts, avg_speed_mps, load_score, intensity, source, added_weight
                FROM set_logs
                """,
                "user_id",
                resolved,
            )
            sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
            rows = conn.execute(sql, (*params, limit)).fetchall()
            return [_row_to_dict(row) for row in rows if row is not None]

    def _get_household_total_volume_by_exercise(
        self, exercise_id: str, user_ids: list[str] | None
    ) -> float:
        with self._connect() as conn:
            resolved = self._resolve_household_user_ids(conn, user_ids)
            if resolved == []:
                return 0.0
            where_sql, where_params = self._exercise_predicate(conn, exercise_id)
            sql = f"SELECT COALESCE(SUM(volume), 0) AS value FROM set_logs WHERE {where_sql}"
            sql, in_params = _in_clause_sql(sql, "user_id", resolved, initial_where=True)
            row = conn.execute(sql, (*where_params, *in_params)).fetchone()
            return float(row["value"] if row is not None else 0.0)

    def _get_household_pr_by_exercise(
        self, exercise_id: str, user_ids: list[str] | None
    ) -> float:
        with self._connect() as conn:
            resolved = self._resolve_household_user_ids(conn, user_ids)
            if resolved == []:
                return 0.0
            where_sql, where_params = self._exercise_predicate(conn, exercise_id)
            sql = (
                f"SELECT COALESCE(MAX(weight), 0) AS value FROM set_logs "
                f"WHERE {where_sql} AND COALESCE(metric_type, '{DEFAULT_METRIC_TYPE}') = '{METRIC_TYPE_STRENGTH}'"
            )
            sql, in_params = _in_clause_sql(sql, "user_id", resolved, initial_where=True)
            row = conn.execute(sql, (*where_params, *in_params)).fetchone()
            return float(row["value"] if row is not None else 0.0)

    def _get_exercise_statistics(
        self, user_id: str | None, household_user_ids: list[str] | None
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            global_stats = self._grouped_exercise_aggregates(conn, None)
            personal_stats = (
                self._grouped_exercise_aggregates(conn, [user_id]) if user_id else {}
            )
            resolved_household_user_ids = self._resolve_household_user_ids(
                conn, household_user_ids
            )
            household_stats = self._grouped_exercise_aggregates(
                conn, resolved_household_user_ids
            )

            exercise_ids = sorted(
                set(global_stats) | set(personal_stats) | set(household_stats)
            )
            if not exercise_ids:
                return []

            sql, params = _in_clause_sql(
                "SELECT id, name_en, name_de, metric_type FROM exercises",
                "id",
                exercise_ids,
            )
            exercise_rows = conn.execute(sql, params).fetchall()
            exercise_map: dict[str, dict[str, Any]] = {
                str(row["id"]): dict(row)
                for row in exercise_rows
                if row is not None and row["id"] is not None
            }

            stats: list[dict[str, Any]] = []
            for exercise_id in exercise_ids:
                global_row = global_stats.get(exercise_id, _empty_exercise_aggregate())
                personal_row = personal_stats.get(exercise_id, _empty_exercise_aggregate())
                household_row = household_stats.get(exercise_id, _empty_exercise_aggregate())
                meta = exercise_map.get(exercise_id, {})
                stats.append(
                    {
                        "exercise_id": exercise_id,
                        "name_en": meta.get("name_en"),
                        "name_de": meta.get("name_de"),
                        "metric_type": _normalize_metric_type(
                            meta.get("metric_type") or DEFAULT_METRIC_TYPE
                        ),
                        "total_volume_global": float(global_row["total_volume"]),
                        "total_sets_global": int(global_row["total_sets"]),
                        "pr_global": float(global_row["pr"]),
                        "total_volume_personal": float(personal_row["total_volume"]),
                        "total_sets_personal": int(personal_row["total_sets"]),
                        "pr_personal": float(personal_row["pr"]),
                        "total_volume_household": float(household_row["total_volume"]),
                        "total_sets_household": int(household_row["total_sets"]),
                        "pr_household": float(household_row["pr"]),
                    }
                )
            return stats

    def _get_exercise_metric_statistics(
        self,
        exercise_id: str,
        metric_type: str,
        user_id: str | None,
        user_ids: list[str] | None,
    ) -> dict[str, Any]:
        """Return metric-specific aggregated statistics for one exercise."""
        resolved_metric_type = _normalize_metric_type(metric_type)
        payload = _empty_exercise_metric_statistics(exercise_id, resolved_metric_type)

        with self._connect() as conn:
            where_sql, where_params = self._exercise_predicate(conn, exercise_id)
            scope_sql, scope_params = _scope_filter_sql(user_id, user_ids, "user_id")
            filter_sql = (
                f"{where_sql} AND COALESCE(metric_type, '{DEFAULT_METRIC_TYPE}') = ?{scope_sql}"
            )
            params = (*where_params, resolved_metric_type, *scope_params)

            aggregate_row = conn.execute(
                f"""
                SELECT
                    COUNT(*) AS entry_count,
                    MAX(created_at) AS last_entry_at,
                    COALESCE(SUM(volume), 0) AS total_volume,
                    COUNT(*) AS total_sets,
                    COALESCE(MAX(weight), 0) AS pr_weight,
                    COALESCE(SUM(reps), 0) AS total_reps,
                    COALESCE(MAX(reps), 0) AS best_reps,
                    COALESCE(SUM(COALESCE(added_weight, 0) * COALESCE(reps, 0)), 0) AS total_added_weight_volume,
                    COALESCE(MAX(added_weight), 0) AS best_added_weight,
                    COALESCE(SUM(duration_seconds), 0) AS total_duration_seconds,
                    COALESCE(MAX(duration_seconds), 0) AS best_duration_seconds,
                    COALESCE(SUM(distance_m), 0) AS total_distance_m,
                    COALESCE(MAX(distance_m), 0) AS best_distance_m,
                    MIN(
                        CASE
                            WHEN duration_seconds > 0 AND distance_m > 0
                                THEN (duration_seconds * 1000.0) / distance_m
                            ELSE NULL
                        END
                    ) AS best_pace_seconds_per_km,
                    COALESCE(SUM(calories), 0) AS total_calories,
                    COALESCE(SUM(steps), 0) AS total_steps,
                    COALESCE(MAX(max_heart_rate), 0) AS max_heart_rate,
                    AVG(avg_heart_rate) AS avg_heart_rate_simple,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN avg_heart_rate IS NOT NULL AND duration_seconds IS NOT NULL AND duration_seconds > 0
                                    THEN avg_heart_rate * duration_seconds
                                ELSE 0
                            END
                        ),
                        0
                    ) AS hr_weighted_sum,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN avg_heart_rate IS NOT NULL AND duration_seconds IS NOT NULL AND duration_seconds > 0
                                    THEN duration_seconds
                                ELSE 0
                            END
                        ),
                        0
                    ) AS hr_weighted_duration,
                    AVG(avg_power_watts) AS avg_power_watts,
                    COALESCE(MAX(max_power_watts), 0) AS max_power_watts,
                    AVG(avg_speed_mps) AS avg_speed_mps,
                    COALESCE(SUM(load_score), 0) AS total_load_score
                FROM set_logs
                WHERE {filter_sql}
                """,
                params,
            ).fetchone()

            if aggregate_row is not None:
                payload["entry_count"] = int(aggregate_row["entry_count"] or 0)
                payload["last_entry_at"] = aggregate_row["last_entry_at"]
                payload["total_volume"] = float(aggregate_row["total_volume"] or 0.0)
                payload["total_sets"] = int(aggregate_row["total_sets"] or 0)
                payload["pr_weight"] = float(aggregate_row["pr_weight"] or 0.0)
                payload["total_reps"] = int(aggregate_row["total_reps"] or 0)
                payload["best_reps"] = int(aggregate_row["best_reps"] or 0)
                payload["total_added_weight_volume"] = float(
                    aggregate_row["total_added_weight_volume"] or 0.0
                )
                payload["best_added_weight"] = float(
                    aggregate_row["best_added_weight"] or 0.0
                )
                payload["total_duration_seconds"] = int(
                    aggregate_row["total_duration_seconds"] or 0
                )
                payload["best_duration_seconds"] = int(
                    aggregate_row["best_duration_seconds"] or 0
                )
                payload["total_distance_m"] = float(aggregate_row["total_distance_m"] or 0.0)
                payload["best_distance_m"] = float(aggregate_row["best_distance_m"] or 0.0)
                pace_raw = aggregate_row["best_pace_seconds_per_km"]
                payload["best_pace_seconds_per_km"] = (
                    float(pace_raw) if pace_raw is not None else 0.0
                )
                payload["total_calories"] = float(aggregate_row["total_calories"] or 0.0)
                payload["total_steps"] = int(aggregate_row["total_steps"] or 0)
                payload["max_heart_rate"] = float(aggregate_row["max_heart_rate"] or 0.0)
                hr_weighted_sum = float(aggregate_row["hr_weighted_sum"] or 0.0)
                hr_weighted_duration = float(aggregate_row["hr_weighted_duration"] or 0.0)
                if hr_weighted_duration > 0:
                    payload["avg_heart_rate"] = hr_weighted_sum / hr_weighted_duration
                else:
                    avg_hr_simple = aggregate_row["avg_heart_rate_simple"]
                    payload["avg_heart_rate"] = (
                        float(avg_hr_simple) if avg_hr_simple is not None else 0.0
                    )
                avg_power_raw = aggregate_row["avg_power_watts"]
                payload["avg_power_watts"] = (
                    float(avg_power_raw) if avg_power_raw is not None else 0.0
                )
                payload["max_power_watts"] = float(aggregate_row["max_power_watts"] or 0.0)
                avg_speed_raw = aggregate_row["avg_speed_mps"]
                payload["avg_speed_mps"] = (
                    float(avg_speed_raw) if avg_speed_raw is not None else 0.0
                )
                payload["total_load_score"] = float(aggregate_row["total_load_score"] or 0.0)

            last_row = conn.execute(
                f"""
                SELECT
                    exercise_id,
                    exercise,
                    metric_type,
                    weight,
                    reps,
                    duration_seconds,
                    distance_m,
                    calories,
                    steps,
                    avg_heart_rate,
                    max_heart_rate,
                    load_score,
                    intensity,
                    added_weight,
                    created_at
                FROM set_logs
                WHERE {filter_sql}
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
            if last_row is not None:
                payload["last_entry"] = _row_to_dict(last_row) or {}
                payload["last_entry_summary"] = _exercise_last_entry_summary(
                    payload["last_entry"], resolved_metric_type
                )

            top_exercise_name = conn.execute(
                "SELECT name_en, name_de FROM exercises WHERE id = ? LIMIT 1",
                (exercise_id,),
            ).fetchone()
            if top_exercise_name is not None:
                payload["name_en"] = top_exercise_name["name_en"]
                payload["name_de"] = top_exercise_name["name_de"]

        return payload

    def _grouped_exercise_aggregates(
        self, conn: sqlite3.Connection, user_ids: list[str] | None
    ) -> dict[str, dict[str, float | int]]:
        sql = """
            SELECT
                exercise_id,
                COALESCE(SUM(volume), 0) AS total_volume,
                COUNT(*) AS total_sets,
                COALESCE(
                    MAX(
                        CASE
                            WHEN COALESCE(metric_type, 'strength') = 'strength' THEN weight
                            ELSE NULL
                        END
                    ),
                    0
                ) AS pr
            FROM set_logs
            WHERE exercise_id IS NOT NULL
              AND TRIM(exercise_id) != ''
        """
        params: tuple[Any, ...] = ()
        if user_ids is not None:
            sql, params = _in_clause_sql(sql, "user_id", user_ids, initial_where=True)
            if not user_ids:
                return {}

        sql += " GROUP BY exercise_id ORDER BY exercise_id ASC"
        rows = conn.execute(sql, params).fetchall()
        result: dict[str, dict[str, float | int]] = {}
        for row in rows:
            if row is None or row["exercise_id"] is None:
                continue
            exercise_id = str(row["exercise_id"])
            result[exercise_id] = {
                "total_volume": float(row["total_volume"]),
                "total_sets": int(row["total_sets"]),
                "pr": float(row["pr"]),
            }
        return result

    def _get_household_equipment_statistics(
        self, user_ids: list[str] | None
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            resolved = self._resolve_household_user_ids(conn, user_ids)
            return self._get_equipment_statistics(conn, resolved)

    def _get_equipment_statistics(
        self, conn_or_user_ids: sqlite3.Connection | list[str] | None, user_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        if isinstance(conn_or_user_ids, sqlite3.Connection):
            conn = conn_or_user_ids
            target_user_ids = user_ids
        else:
            with self._connect() as conn:
                self._seed_default_equipment(conn)
                return self._get_equipment_statistics(conn, conn_or_user_ids)

        self._seed_default_equipment(conn)
        join_user_filter = ""
        params: tuple[Any, ...] = ()
        if target_user_ids is not None:
            if not target_user_ids:
                join_user_filter = " AND 1 = 0"
            else:
                placeholders = ",".join("?" for _ in target_user_ids)
                join_user_filter = f" AND sl.user_id IN ({placeholders})"
                params = tuple(target_user_ids)

        sql = f"""
            SELECT
                eq.id AS equipment_id,
                eq.name AS equipment_name,
                eq.name_en AS equipment_name_en,
                eq.name_de AS equipment_name_de,
                eq.icon AS equipment_icon,
                eq.location AS equipment_location,
                eq.enabled AS equipment_enabled,
                COALESCE(SUM(sl.volume), 0) AS total_volume,
                COUNT(sl.id) AS total_sets,
                COUNT(DISTINCT sl.workout_id) AS total_trainings,
                MAX(sl.created_at) AS last_used
            FROM equipment eq
            LEFT JOIN set_logs sl
                ON sl.equipment_id = eq.id
                {join_user_filter}
        """
        sql += """
            GROUP BY eq.id, eq.name, eq.name_en, eq.name_de, eq.icon, eq.location, eq.enabled
            ORDER BY eq.sort_order ASC, COALESCE(eq.name_de, eq.name_en, eq.name, eq.id) COLLATE NOCASE ASC, eq.id ASC
        """

        rows = conn.execute(sql, params).fetchall()
        stats: list[dict[str, Any]] = []
        for row in rows:
            if row is None:
                continue
            equipment_id = str(row["equipment_id"])
            top_exercise_sql = """
                SELECT
                    sl.exercise_id AS exercise_id,
                    ex.name_en AS exercise_name_en,
                    ex.name_de AS exercise_name_de,
                    COUNT(*) AS set_count
                FROM set_logs sl
                LEFT JOIN exercises ex ON ex.id = sl.exercise_id
                WHERE sl.equipment_id = ?
            """
            top_params: tuple[Any, ...] = (equipment_id,)
            if target_user_ids is not None:
                if not target_user_ids:
                    top_exercise_sql += " AND 1 = 0"
                else:
                    placeholders = ",".join("?" for _ in target_user_ids)
                    top_exercise_sql += f" AND sl.user_id IN ({placeholders})"
                    top_params = (equipment_id, *target_user_ids)
            top_exercise_sql += """
                GROUP BY sl.exercise_id, ex.name_en, ex.name_de
                ORDER BY set_count DESC, sl.exercise_id ASC
                LIMIT 1
            """
            top_exercise_row = conn.execute(top_exercise_sql, top_params).fetchone()
            top_exercise = None
            if top_exercise_row is not None:
                top_exercise = {
                    "exercise_id": top_exercise_row["exercise_id"],
                    "name_en": top_exercise_row["exercise_name_en"],
                    "name_de": top_exercise_row["exercise_name_de"],
                    "set_count": int(top_exercise_row["set_count"]),
                }
            stats.append(
                {
                    "equipment_id": equipment_id,
                    "name": row["equipment_name"],
                    "name_en": row["equipment_name_en"],
                    "name_de": row["equipment_name_de"],
                    "icon": row["equipment_icon"],
                    "location": row["equipment_location"],
                    "enabled": int(row["equipment_enabled"]) == 1,
                    "total_volume": float(row["total_volume"]),
                    "total_sets": int(row["total_sets"]),
                    "total_trainings": int(row["total_trainings"]),
                    "last_used": row["last_used"],
                    "top_exercise": top_exercise,
                }
            )
        return stats

    def _resolve_equipment_for_exercise(
        self, conn: sqlite3.Connection, exercise_id: str
    ) -> str | None:
        row = conn.execute(
            """
            SELECT equipment_id
            FROM exercises
            WHERE id = ?
            LIMIT 1
            """,
            (exercise_id,),
        ).fetchone()
        if row is None or row["equipment_id"] is None:
            return None
        equipment_id = str(row["equipment_id"]).strip()
        return equipment_id if equipment_id else None

    def _seed_default_equipment(self, conn: sqlite3.Connection) -> None:
        now = _isoformat(datetime.now(timezone.utc))
        for item in DEFAULT_EQUIPMENT:
            default_name_en = str(item.get("name_en") or item.get("name") or item["id"])
            default_name_de = str(item.get("name_de") or item.get("name") or default_name_en)
            default_name = str(item.get("name") or default_name_de or default_name_en)
            conn.execute(
                """
                INSERT INTO equipment(
                    id, name, name_en, name_de, description, icon, location, enabled, sort_order, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = CASE
                        WHEN equipment.name IS NULL OR TRIM(equipment.name) = '' THEN excluded.name
                        ELSE equipment.name
                    END,
                    name_en = CASE
                        WHEN equipment.name_en IS NULL OR TRIM(equipment.name_en) = '' THEN excluded.name_en
                        ELSE equipment.name_en
                    END,
                    name_de = CASE
                        WHEN equipment.name_de IS NULL OR TRIM(equipment.name_de) = '' THEN excluded.name_de
                        ELSE equipment.name_de
                    END,
                    icon = COALESCE(equipment.icon, excluded.icon),
                    sort_order = excluded.sort_order
                """,
                (
                    str(item["id"]),
                    default_name,
                    default_name_en,
                    default_name_de,
                    item["description"],
                    item["icon"],
                    item["location"],
                    1 if bool(item.get("enabled", True)) else 0,
                    int(item.get("sort_order", 100)),
                    now,
                ),
            )
        conn.commit()

    def _seed_default_muscle_groups(self, conn: sqlite3.Connection) -> None:
        now = _isoformat(datetime.now(timezone.utc))
        for item in DEFAULT_MUSCLE_GROUPS:
            conn.execute(
                """
                INSERT INTO muscle_groups(
                    id, name_en, name_de, description, icon, body_region,
                    enabled, sort_order, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (
                    str(item["id"]),
                    str(item["name_en"]),
                    item.get("name_de"),
                    item.get("description"),
                    item.get("icon"),
                    item.get("body_region"),
                    1 if bool(item.get("enabled", True)) else 0,
                    int(item.get("sort_order", 100)),
                    now,
                    now,
                ),
            )
        self._seed_default_exercise_muscle_groups(conn, now)
        conn.commit()

    def _seed_default_exercise_muscle_groups(
        self, conn: sqlite3.Connection, now: str
    ) -> None:
        for exercise_id, mappings in DEFAULT_EXERCISE_MUSCLE_GROUP_MAP.items():
            for mapping in mappings:
                role = _normalize_muscle_role(str(mapping.get("role") or MUSCLE_ROLE_PRIMARY))
                weight_factor = _resolve_weight_factor(
                    role, float(mapping.get("weight_factor", 1.0))
                )
                conn.execute(
                    """
                    INSERT INTO exercise_muscle_groups(
                        exercise_id, muscle_group_id, role, weight_factor, created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?)
                    ON CONFLICT(exercise_id, muscle_group_id) DO NOTHING
                    """,
                    (
                        exercise_id,
                        str(mapping["muscle_group_id"]),
                        role,
                        weight_factor,
                        now,
                        now,
                    ),
                )

    def _weighted_muscle_group_aggregates(
        self, conn: sqlite3.Connection, user_ids: list[str] | None
    ) -> dict[str, dict[str, Any]]:
        sql = """
            SELECT
                emg.muscle_group_id AS muscle_group_id,
                COALESCE(SUM(sl.volume * emg.weight_factor), 0) AS total_volume,
                COUNT(sl.id) AS total_sets,
                MAX(sl.created_at) AS last_used
            FROM exercise_muscle_groups emg
            LEFT JOIN set_logs sl ON sl.exercise_id = emg.exercise_id
        """
        params: tuple[Any, ...] = ()
        if user_ids is not None:
            if not user_ids:
                return {}
            placeholders = ",".join("?" for _ in user_ids)
            sql += f" AND sl.user_id IN ({placeholders})"
            params = tuple(user_ids)
        sql += " GROUP BY emg.muscle_group_id"
        rows = conn.execute(sql, params).fetchall()

        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            if row is None or row["muscle_group_id"] is None:
                continue
            muscle_group_id = str(row["muscle_group_id"])
            result[muscle_group_id] = {
                "total_volume": float(row["total_volume"]),
                "total_sets": int(row["total_sets"]),
                "last_used": row["last_used"],
                "top_exercise": self._top_exercise_for_muscle_group(
                    conn, muscle_group_id, user_ids
                ),
            }
        return result

    def _top_exercise_for_muscle_group(
        self, conn: sqlite3.Connection, muscle_group_id: str, user_ids: list[str] | None
    ) -> dict[str, Any] | None:
        sql = """
            SELECT
                emg.exercise_id AS exercise_id,
                ex.name_en AS name_en,
                ex.name_de AS name_de,
                COALESCE(SUM(sl.volume * emg.weight_factor), 0) AS weighted_volume
            FROM exercise_muscle_groups emg
            LEFT JOIN set_logs sl ON sl.exercise_id = emg.exercise_id
            LEFT JOIN exercises ex ON ex.id = emg.exercise_id
            WHERE emg.muscle_group_id = ?
        """
        params: list[Any] = [muscle_group_id]
        if user_ids is not None:
            if not user_ids:
                return None
            placeholders = ",".join("?" for _ in user_ids)
            sql += f" AND sl.user_id IN ({placeholders})"
            params.extend(user_ids)
        sql += """
            GROUP BY emg.exercise_id, ex.name_en, ex.name_de
            HAVING COALESCE(SUM(sl.volume * emg.weight_factor), 0) > 0
            ORDER BY weighted_volume DESC, emg.exercise_id ASC
            LIMIT 1
        """
        row = conn.execute(sql, tuple(params)).fetchone()
        if row is None or row["exercise_id"] is None:
            return None
        return {
            "exercise_id": row["exercise_id"],
            "name_en": row["name_en"],
            "name_de": row["name_de"],
            "weighted_volume": float(row["weighted_volume"]),
        }

    def _resolve_household_user_ids(
        self, conn: sqlite3.Connection, user_ids: list[str] | None
    ) -> list[str]:
        if user_ids is not None:
            return user_ids

        rows = conn.execute(
            "SELECT id FROM users WHERE enabled = 1 ORDER BY created_at ASC"
        ).fetchall()
        resolved = [
            str(row["id"])
            for row in rows
            if row["id"] is not None and str(row["id"]) != ""
        ]
        if not resolved:
            _LOGGER.debug(
                "HAGym: no enabled users found in users table, falling back to legacy user"
            )
            return [LEGACY_USER_ID]
        return resolved

    def _exercise_predicate(
        self, conn: sqlite3.Connection, exercise_id: str
    ) -> tuple[str, tuple[Any, ...]]:
        aliases = self._exercise_aliases(conn, exercise_id)
        if aliases:
            placeholders = ",".join("?" for _ in aliases)
            return (
                f"(exercise_id = ? OR (exercise_id IS NULL AND lower(trim(exercise)) IN ({placeholders})))",
                (exercise_id, *aliases),
            )
        return ("exercise_id = ?", (exercise_id,))

    def _exercise_aliases(self, conn: sqlite3.Connection, exercise_id: str) -> list[str]:
        row = conn.execute(
            """
            SELECT id, name_en, name_de
            FROM exercises
            WHERE id = ?
            LIMIT 1
            """,
            (exercise_id,),
        ).fetchone()
        aliases: list[str] = [exercise_id.strip().lower()]
        if row is not None:
            name_en = row["name_en"]
            name_de = row["name_de"]
            if name_en:
                aliases.append(str(name_en).strip().lower())
            if name_de:
                aliases.append(str(name_de).strip().lower())
        return list(dict.fromkeys([alias for alias in aliases if alias]))

    def _read_float(self, sql: str, params: tuple[Any, ...] = ()) -> float:
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return float(row["value"] if row is not None else 0.0)

    def _read_int(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return int(row["value"] if row is not None else 0)

    def _connect(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        except sqlite3.Error:
            if conn is not None:
                conn.close()
            _LOGGER.exception("HAGym: failed to open sqlite database at %s", self._db_path)
            raise


def _in_clause_sql(
    base_sql: str,
    column: str,
    values: list[str] | None,
    *,
    initial_where: bool = False,
) -> tuple[str, tuple[Any, ...]]:
    if values is None:
        return base_sql, ()
    if not values:
        empty_sql = f"{base_sql} {'AND' if initial_where else 'WHERE'} 1 = 0"
        return empty_sql, ()

    placeholders = ",".join("?" for _ in values)
    connector = "AND" if initial_where else "WHERE"
    sql = f"{base_sql} {connector} {column} IN ({placeholders})"
    return sql, tuple(values)


def _scope_filter_sql(
    user_id: str | None,
    user_ids: list[str] | None,
    column: str,
) -> tuple[str, tuple[Any, ...]]:
    """Return SQL suffix and params for one-user / multi-user / global scope."""
    if user_id is not None:
        return f" AND {column} = ?", (user_id,)
    if user_ids is None:
        return "", ()
    if not user_ids:
        return " AND 1 = 0", ()
    placeholders = ",".join("?" for _ in user_ids)
    return f" AND {column} IN ({placeholders})", tuple(user_ids)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert sqlite row to dict and keep None unchanged."""
    if row is None:
        return None
    return dict(row)


def _clean_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _resolve_equipment_names(
    *,
    name: str | None,
    name_en: str | None,
    name_de: str | None,
    existing: dict[str, Any] | None = None,
) -> tuple[str, str, str]:
    existing_name = _clean_optional_text(existing.get("name") if existing else None)
    existing_name_en = _clean_optional_text(existing.get("name_en") if existing else None)
    existing_name_de = _clean_optional_text(existing.get("name_de") if existing else None)

    resolved_name = _clean_optional_text(name)
    resolved_name_en = _clean_optional_text(name_en)
    resolved_name_de = _clean_optional_text(name_de)

    if resolved_name and resolved_name_en is None and resolved_name_de is None:
        resolved_name_en = resolved_name
        resolved_name_de = resolved_name
    if resolved_name_de and resolved_name_en is None:
        resolved_name_en = resolved_name_de
    if resolved_name_en and resolved_name_de is None:
        resolved_name_de = resolved_name_en

    if resolved_name_en is None:
        resolved_name_en = existing_name_en or existing_name_de or existing_name
    if resolved_name_de is None:
        resolved_name_de = existing_name_de or existing_name_en or existing_name or resolved_name_en
    if resolved_name_en is None:
        resolved_name_en = resolved_name_de
    if resolved_name_de is None:
        resolved_name_de = resolved_name_en

    if resolved_name_en is None or resolved_name_de is None:
        raise ValueError("At least one equipment name must be provided.")

    # Keep legacy compatibility column populated, prefer German name.
    resolved_legacy_name = resolved_name_de or resolved_name_en
    return resolved_name_en, resolved_name_de, resolved_legacy_name


def _empty_exercise_aggregate() -> dict[str, float | int]:
    """Return zero-valued aggregate metrics for exercises without logged sets."""
    return {"total_volume": 0.0, "total_sets": 0, "pr": 0.0}


def _empty_exercise_metric_statistics(
    exercise_id: str, metric_type: str
) -> dict[str, Any]:
    """Return zero-valued metric-aware statistics payload."""
    return {
        "exercise_id": exercise_id,
        "metric_type": metric_type,
        "entry_count": 0,
        "last_entry_at": None,
        "last_entry_summary": None,
        "last_entry": None,
        "name_en": None,
        "name_de": None,
        "total_volume": 0.0,
        "total_sets": 0,
        "pr_weight": 0.0,
        "total_reps": 0,
        "best_reps": 0,
        "total_added_weight_volume": 0.0,
        "best_added_weight": 0.0,
        "total_duration_seconds": 0,
        "best_duration_seconds": 0,
        "total_distance_m": 0.0,
        "best_distance_m": 0.0,
        "best_pace_seconds_per_km": 0.0,
        "total_calories": 0.0,
        "total_steps": 0,
        "avg_heart_rate": 0.0,
        "max_heart_rate": 0.0,
        "avg_power_watts": 0.0,
        "max_power_watts": 0.0,
        "avg_speed_mps": 0.0,
        "total_load_score": 0.0,
    }


def _empty_daily_metric_bucket(day_range: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": str(day_range.get("date") or ""),
        "day_start": day_range.get("day_start_local"),
        "day_end": day_range.get("day_end_local"),
        "weekday": str(day_range.get("weekday") or ""),
        "entry_count": 0,
        "workout_count": 0,
        "active": False,
        "total_load_score": 0.0,
        "total_activity_load_score": 0.0,
        "total_strength_volume_kg": 0.0,
        "total_minutes": 0.0,
        "total_distance_km": 0.0,
        "total_calories": 0.0,
        "total_steps": 0,
        "total_reps": 0,
        "total_sets": 0,
        "strength_volume_kg": 0.0,
        "strength_sets": 0,
        "strength_reps": 0,
        "bodyweight_reps": 0,
        "bodyweight_entries": 0,
        "bodyweight_load_score": 0.0,
        "duration_minutes": 0.0,
        "duration_entries": 0,
        "duration_load_score": 0.0,
        "hold_minutes": 0.0,
        "hold_entries": 0,
        "hold_load_score": 0.0,
        "distance_km": 0.0,
        "distance_minutes": 0.0,
        "distance_entries": 0,
        "distance_load_score": 0.0,
        "cardio_minutes": 0.0,
        "cardio_km": 0.0,
        "cardio_calories": 0.0,
        "cardio_steps": 0,
        "cardio_entries": 0,
        "cardio_load_score": 0.0,
        "cardio_avg_heart_rate": 0.0,
        "cardio_max_heart_rate": 0.0,
        "custom_minutes": 0.0,
        "custom_km": 0.0,
        "custom_entries": 0,
        "custom_load_score": 0.0,
        "top_exercise_id": None,
        "top_exercise_name": None,
        "top_exercise_metric_type": None,
        "top_exercise_value": 0.0,
        "top_equipment_id": None,
        "top_equipment_name": None,
        "top_equipment_value": 0.0,
        "top_muscle_group_id": None,
        "top_muscle_group_name": None,
        "top_muscle_group_value": 0.0,
        "exercises": [],
        "equipment": [],
        "muscle_groups": [],
        "_cardio_hr_duration_weighted_sum": 0.0,
        "_cardio_hr_duration_weight": 0.0,
        "_cardio_hr_simple_sum": 0.0,
        "_cardio_hr_simple_count": 0,
    }


def _metric_aggregate_value(row: dict[str, Any] | None) -> float:
    if not row:
        return 0.0
    return float(
        row.get("strength_volume_kg", 0.0) or 0.0
    ) + float(row.get("activity_load_score", 0.0) or 0.0)


def _empty_weighted_muscle_aggregate() -> dict[str, Any]:
    """Return zero-valued aggregate metrics for muscle groups without logged sets."""
    return {
        "total_volume": 0.0,
        "total_sets": 0,
        "last_used": None,
        "top_exercise": None,
    }


def _normalize_muscle_role(role: str) -> str:
    """Normalize mapping role to one of the supported role values."""
    normalized = role.strip().lower()
    if normalized in (MUSCLE_ROLE_PRIMARY, MUSCLE_ROLE_SECONDARY, MUSCLE_ROLE_STABILIZER):
        return normalized
    return MUSCLE_ROLE_PRIMARY


def _resolve_weight_factor(role: str, weight_factor: float) -> float:
    """Normalize mapping weight factor and apply role defaults for invalid values."""
    try:
        resolved = float(weight_factor)
    except (TypeError, ValueError):
        resolved = DEFAULT_MUSCLE_ROLE_WEIGHT_FACTORS.get(role, 1.0)
    if resolved <= 0:
        return DEFAULT_MUSCLE_ROLE_WEIGHT_FACTORS.get(role, 1.0)
    return resolved


def _normalize_metric_type(metric_type: Any) -> str:
    normalized = str(metric_type or DEFAULT_METRIC_TYPE).strip().lower()
    if normalized in SUPPORTED_METRIC_TYPES:
        return normalized
    return DEFAULT_METRIC_TYPE


def _exercise_last_entry_summary(last_entry: dict[str, Any], metric_type: str) -> str:
    exercise_name = str(last_entry.get("exercise") or last_entry.get("exercise_id") or "Exercise")
    weight = float(last_entry.get("weight") or 0.0)
    reps = int(last_entry.get("reps") or 0)
    duration_seconds = int(last_entry.get("duration_seconds") or 0)
    distance_m = float(last_entry.get("distance_m") or 0.0)
    avg_hr = float(last_entry.get("avg_heart_rate") or 0.0)

    if metric_type == METRIC_TYPE_STRENGTH:
        return f"{exercise_name} - {weight:.1f} kg x {reps}"
    if metric_type == METRIC_TYPE_BODYWEIGHT:
        return f"{exercise_name} - {reps} reps"
    if metric_type in (METRIC_TYPE_DURATION, METRIC_TYPE_HOLD):
        return f"{exercise_name} - {_format_mmss(duration_seconds)} min"
    if metric_type == METRIC_TYPE_DISTANCE:
        distance_km = distance_m / 1000.0
        if duration_seconds > 0:
            return f"{exercise_name} - {distance_km:.1f} km in {_format_mmss(duration_seconds)} min"
        return f"{exercise_name} - {distance_km:.1f} km"
    if metric_type == METRIC_TYPE_CARDIO:
        distance_km = distance_m / 1000.0
        parts = [f"{exercise_name} - {_format_mmss(duration_seconds)} min"]
        if distance_km > 0:
            parts.append(f"{distance_km:.1f} km")
        if avg_hr > 0:
            parts.append(f"Ø {avg_hr:.0f} bpm")
        return " · ".join(parts)
    return exercise_name


def _format_mmss(total_seconds: int) -> str:
    if total_seconds <= 0:
        return "0:00"
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def _cardio_intensity_factor(intensity: str | None) -> float:
    normalized = str(intensity or "").strip().lower()
    if normalized == "low":
        return 0.8
    if normalized == "moderate":
        return 1.0
    if normalized == "hard":
        return 1.4
    if normalized == "very_hard":
        return 1.8
    return 1.0


def _parse_iso_datetime(value: Any) -> datetime | None:
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


def _isoformat(value: datetime) -> str:
    """Return an ISO 8601 UTC timestamp string for sqlite storage."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()
