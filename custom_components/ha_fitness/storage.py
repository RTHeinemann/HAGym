"""SQLite storage layer for HAGym."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import sqlite3
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    DEFAULT_EQUIPMENT,
    DEFAULT_EXERCISE_MUSCLE_GROUP_MAP,
    DEFAULT_EXERCISE_EQUIPMENT_MAP,
    DEFAULT_EXERCISES,
    DEFAULT_MUSCLE_GROUPS,
    DEFAULT_MUSCLE_ROLE_WEIGHT_FACTORS,
    MUSCLE_ROLE_PRIMARY,
    MUSCLE_ROLE_SECONDARY,
    MUSCLE_ROLE_STABILIZER,
    LEGACY_USER_ID,
)
from .migrations import apply_migrations

_LOGGER = logging.getLogger(__name__)


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
        enabled: bool = True,
        sort_order: int = 0,
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
            enabled,
            sort_order,
        )

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
        """Update one exercise row and return whether a row was modified."""
        return await self._hass.async_add_executor_job(
            self._update_exercise,
            exercise_id,
            name_en,
            name_de,
            muscle_group,
            equipment,
            equipment_id,
            enabled,
            sort_order,
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
        name: str,
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
        """Replace all muscle mappings for one exercise from role buckets."""
        await self._hass.async_add_executor_job(
            self._replace_muscle_groups_for_exercise,
            exercise_id,
            primary_ids,
            secondary_ids,
            stabilizer_ids,
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
                INSERT INTO workouts(user_id, started_at, finished_at, created_at)
                VALUES(?, ?, NULL, ?)
                """,
                (user_id, iso_started_at, iso_started_at),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def _finish_workout(self, workout_id: int, finished_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE workouts SET finished_at = ? WHERE id = ?",
                (_isoformat(finished_at), workout_id),
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
    ) -> int:
        with self._connect() as conn:
            resolved_equipment_id = equipment_id
            if (resolved_equipment_id is None or str(resolved_equipment_id).strip() == "") and exercise_id:
                resolved_equipment_id = self._resolve_equipment_for_exercise(conn, exercise_id)
            cursor = conn.execute(
                """
                INSERT INTO set_logs(
                    user_id, workout_id, exercise, exercise_id, equipment_id, weight, reps, volume, notes, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    workout_id,
                    exercise,
                    exercise_id,
                    resolved_equipment_id,
                    weight,
                    reps,
                    volume,
                    notes,
                    _isoformat(created_at),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def _get_last_set(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, workout_id, exercise, exercise_id, equipment_id, weight, reps, volume, notes, created_at
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
                SELECT id, user_id, workout_id, exercise, exercise_id, equipment_id, weight, reps, volume, notes, created_at
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
                SELECT id, user_id, started_at, finished_at, created_at
                FROM workouts
                WHERE finished_at IS NULL
                  AND user_id = ?
                ORDER BY started_at DESC, id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            return _row_to_dict(row)

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
            sql = f"SELECT COALESCE(MAX(weight), 0) AS value FROM set_logs WHERE {where_sql}"
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
            SELECT id, user_id, workout_id, exercise, exercise_id, equipment_id, weight, reps, volume, notes, created_at
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
            SELECT id, name_en, name_de, muscle_group, equipment, equipment_id, enabled, sort_order, created_at
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
                SELECT id, name_en, name_de, muscle_group, equipment, equipment_id, enabled, sort_order, created_at
                FROM exercises
                WHERE id = ?
                LIMIT 1
                """,
                (exercise_id,),
            ).fetchone()
            if row is None:
                return None
            return _row_to_dict(row)

    def _add_exercise(
        self,
        exercise_id: str,
        name_en: str,
        name_de: str | None,
        muscle_group: str | None,
        equipment: str | None,
        equipment_id: str | None,
        enabled: bool,
        sort_order: int,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO exercises(
                    id, name_en, name_de, muscle_group, equipment, equipment_id, enabled, sort_order, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name_en = excluded.name_en,
                    name_de = excluded.name_de,
                    muscle_group = excluded.muscle_group,
                    equipment = excluded.equipment,
                    equipment_id = COALESCE(excluded.equipment_id, exercises.equipment_id),
                    enabled = excluded.enabled,
                    sort_order = excluded.sort_order
                """,
                (
                    exercise_id,
                    name_en,
                    name_de,
                    muscle_group,
                    equipment,
                    equipment_id,
                    1 if enabled else 0,
                    sort_order,
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
        if muscle_group is not None:
            updates.append("muscle_group = ?")
            params.append(muscle_group)
        if equipment is not None:
            updates.append("equipment = ?")
            params.append(equipment)
        if equipment_id is not None:
            updates.append("equipment_id = ?")
            params.append(equipment_id)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)
        if sort_order is not None:
            updates.append("sort_order = ?")
            params.append(sort_order)
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
                        id, name_en, name_de, muscle_group, equipment, equipment_id, enabled, sort_order, created_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name_en = excluded.name_en,
                        name_de = excluded.name_de,
                        muscle_group = excluded.muscle_group,
                        equipment = excluded.equipment,
                        equipment_id = COALESCE(exercises.equipment_id, excluded.equipment_id),
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
                        int(exercise["sort_order"]),
                        now,
                    ),
                )
            conn.commit()

    def _add_equipment(
        self,
        equipment_id: str,
        name: str,
        description: str | None,
        icon: str | None,
        location: str | None,
        enabled: bool,
        sort_order: int,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO equipment(id, name, description, icon, location, enabled, sort_order, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    icon = excluded.icon,
                    location = excluded.location,
                    enabled = excluded.enabled,
                    sort_order = excluded.sort_order
                """,
                (
                    equipment_id,
                    name,
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
        description: str | None,
        icon: str | None,
        location: str | None,
        enabled: bool | None,
        sort_order: int | None,
    ) -> bool:
        updates: list[str] = []
        params: list[Any] = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
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
                SELECT id, name, description, icon, location, enabled, sort_order, created_at
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
                SELECT id, name, description, icon, location, enabled, sort_order, created_at
                FROM equipment
                ORDER BY enabled DESC, sort_order ASC, name COLLATE NOCASE ASC, id ASC
                """
            ).fetchall()
            return [_row_to_dict(row) for row in rows if row is not None]

    def _get_enabled_equipment(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self._seed_default_equipment(conn)
            rows = conn.execute(
                """
                SELECT id, name, description, icon, location, enabled, sort_order, created_at
                FROM equipment
                WHERE enabled = 1
                ORDER BY sort_order ASC, name COLLATE NOCASE ASC, id ASC
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
            SELECT id, name_en, name_de, muscle_group, equipment, equipment_id, enabled, sort_order, created_at
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
                SELECT id, user_id, workout_id, exercise, exercise_id, equipment_id, weight, reps, volume, notes, created_at
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
            sql = f"SELECT COALESCE(MAX(weight), 0) AS value FROM set_logs WHERE {where_sql}"
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
                "SELECT id, name_en, name_de FROM exercises",
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

    def _grouped_exercise_aggregates(
        self, conn: sqlite3.Connection, user_ids: list[str] | None
    ) -> dict[str, dict[str, float | int]]:
        sql = """
            SELECT
                exercise_id,
                COALESCE(SUM(volume), 0) AS total_volume,
                COUNT(*) AS total_sets,
                COALESCE(MAX(weight), 0) AS pr
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
            GROUP BY eq.id, eq.name, eq.icon, eq.location, eq.enabled
            ORDER BY eq.sort_order ASC, eq.name COLLATE NOCASE ASC, eq.id ASC
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
            conn.execute(
                """
                INSERT INTO equipment(id, name, description, icon, location, enabled, sort_order, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    icon = COALESCE(equipment.icon, excluded.icon),
                    sort_order = excluded.sort_order
                """,
                (
                    str(item["id"]),
                    str(item["name"]),
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


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert sqlite row to dict and keep None unchanged."""
    if row is None:
        return None
    return dict(row)


def _empty_exercise_aggregate() -> dict[str, float | int]:
    """Return zero-valued aggregate metrics for exercises without logged sets."""
    return {"total_volume": 0.0, "total_sets": 0, "pr": 0.0}


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


def _isoformat(value: datetime) -> str:
    """Return an ISO 8601 UTC timestamp string for sqlite storage."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()
