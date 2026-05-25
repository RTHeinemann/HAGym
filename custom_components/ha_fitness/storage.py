"""SQLite storage layer for HA Fitness Tracker."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import sqlite3
from typing import Any

from homeassistant.core import HomeAssistant

from .const import DEFAULT_EXERCISES, LEGACY_USER_ID
from .migrations import apply_migrations

_LOGGER = logging.getLogger(__name__)


class HAFitnessStore:
    """SQLite-backed persistence helper for HA Fitness."""

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
            enabled,
            sort_order,
        )

    async def async_disable_exercise(self, exercise_id: str) -> bool:
        """Disable one exercise by id."""
        return await self._hass.async_add_executor_job(self._disable_exercise, exercise_id)

    async def async_refresh_exercises(self) -> None:
        """Re-seed built-in catalog entries."""
        await self._hass.async_add_executor_job(self._refresh_exercises)

    async def async_get_exercise_statistics(
        self, user_id: str | None = None, household_user_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Return grouped exercise stats for global/personal/household scopes."""
        return await self._hass.async_add_executor_job(
            self._get_exercise_statistics, user_id, household_user_ids
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
        weight: float,
        reps: int,
        volume: float,
        notes: str | None,
        created_at: datetime,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO set_logs(
                    user_id, workout_id, exercise, exercise_id, weight, reps, volume, notes, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    workout_id,
                    exercise,
                    exercise_id,
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
                SELECT id, user_id, workout_id, exercise, exercise_id, weight, reps, volume, notes, created_at
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
                SELECT id, user_id, workout_id, exercise, exercise_id, weight, reps, volume, notes, created_at
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
            SELECT id, user_id, workout_id, exercise, exercise_id, weight, reps, volume, notes, created_at
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
            SELECT id, name_en, name_de, muscle_group, equipment, enabled, sort_order, created_at
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
                SELECT id, name_en, name_de, muscle_group, equipment, enabled, sort_order, created_at
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
        enabled: bool,
        sort_order: int,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO exercises(id, name_en, name_de, muscle_group, equipment, enabled, sort_order, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name_en = excluded.name_en,
                    name_de = excluded.name_de,
                    muscle_group = excluded.muscle_group,
                    equipment = excluded.equipment,
                    enabled = excluded.enabled,
                    sort_order = excluded.sort_order
                """,
                (
                    exercise_id,
                    name_en,
                    name_de,
                    muscle_group,
                    equipment,
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
                        id, name_en, name_de, muscle_group, equipment, enabled, sort_order, created_at
                    )
                    VALUES(?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name_en = excluded.name_en,
                        name_de = excluded.name_de,
                        muscle_group = excluded.muscle_group,
                        sort_order = excluded.sort_order,
                        enabled = 1
                    """,
                    (
                        str(exercise["id"]),
                        str(exercise["name_en"]),
                        exercise["name_de"],
                        exercise["muscle_group"],
                        exercise["equipment"],
                        int(exercise["sort_order"]),
                        now,
                    ),
                )
            conn.commit()

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
                SELECT id, user_id, workout_id, exercise, exercise_id, weight, reps, volume, notes, created_at
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
                "HA Fitness: no enabled users found in users table, falling back to legacy user"
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
            _LOGGER.exception("HA Fitness: failed to open sqlite database at %s", self._db_path)
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


def _isoformat(value: datetime) -> str:
    """Return an ISO 8601 UTC timestamp string for sqlite storage."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()
