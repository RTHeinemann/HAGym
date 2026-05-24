"""SQLite storage layer for HA Fitness Tracker."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import sqlite3
from typing import Any

from homeassistant.core import HomeAssistant

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

    async def async_start_workout(self, started_at: datetime) -> int:
        """Create a workout row and return its id."""
        return await self._hass.async_add_executor_job(self._start_workout, started_at)

    async def async_finish_workout(self, workout_id: int, finished_at: datetime) -> None:
        """Mark a workout as finished."""
        await self._hass.async_add_executor_job(self._finish_workout, workout_id, finished_at)

    async def async_save_set(
        self,
        workout_id: int | None,
        exercise: str,
        weight: float,
        reps: int,
        volume: float,
        notes: str | None,
        created_at: datetime,
    ) -> int:
        """Persist a set row and return its id."""
        return await self._hass.async_add_executor_job(
            self._save_set,
            workout_id,
            exercise,
            weight,
            reps,
            volume,
            notes,
            created_at,
        )

    async def async_get_last_set(self) -> dict[str, Any] | None:
        """Return most recent set."""
        return await self._hass.async_add_executor_job(self._get_last_set)

    async def async_get_last_set_for_exercise(self, exercise: str) -> dict[str, Any] | None:
        """Return most recent set for one exercise."""
        return await self._hass.async_add_executor_job(self._get_last_set_for_exercise, exercise)

    async def async_get_current_open_workout(self) -> dict[str, Any] | None:
        """Return open workout where finished_at is NULL."""
        return await self._hass.async_add_executor_job(self._get_current_open_workout)

    async def async_get_total_volume(self) -> float:
        """Return total volume across all sets."""
        return await self._hass.async_add_executor_job(self._get_total_volume)

    async def async_get_total_volume_by_exercise(self, exercise: str) -> float:
        """Return total volume for an exercise."""
        return await self._hass.async_add_executor_job(self._get_total_volume_by_exercise, exercise)

    async def async_get_pr_by_exercise(self, exercise: str) -> float:
        """Return max weight for an exercise."""
        return await self._hass.async_add_executor_job(self._get_pr_by_exercise, exercise)

    async def async_get_set_count(self) -> int:
        """Return set count."""
        return await self._hass.async_add_executor_job(self._get_set_count)

    async def async_get_set_count_for_workout(self, workout_id: int) -> int:
        """Return set count for one workout."""
        return await self._hass.async_add_executor_job(
            self._get_set_count_for_workout, workout_id
        )

    async def async_get_workout_count(self) -> int:
        """Return workout count."""
        return await self._hass.async_add_executor_job(self._get_workout_count)

    async def async_get_recent_sets(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return most recent set rows."""
        return await self._hass.async_add_executor_job(self._get_recent_sets, limit)

    # ------------------------------------------------------------------
    # Sync implementation (executor only)
    # ------------------------------------------------------------------

    def _initialize(self) -> None:
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with self._connect() as conn:
            apply_migrations(conn)
            conn.commit()

    def _start_workout(self, started_at: datetime) -> int:
        iso_started_at = _isoformat(started_at)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO workouts(started_at, finished_at, created_at)
                VALUES(?, NULL, ?)
                """,
                (iso_started_at, iso_started_at),
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
        workout_id: int | None,
        exercise: str,
        weight: float,
        reps: int,
        volume: float,
        notes: str | None,
        created_at: datetime,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO set_logs(workout_id, exercise, weight, reps, volume, notes, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (workout_id, exercise, weight, reps, volume, notes, _isoformat(created_at)),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def _get_last_set(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, workout_id, exercise, weight, reps, volume, notes, created_at
                FROM set_logs
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            return _row_to_dict(row)

    def _get_last_set_for_exercise(self, exercise: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, workout_id, exercise, weight, reps, volume, notes, created_at
                FROM set_logs
                WHERE exercise = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (exercise,),
            ).fetchone()
            return _row_to_dict(row)

    def _get_current_open_workout(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, started_at, finished_at, created_at
                FROM workouts
                WHERE finished_at IS NULL
                ORDER BY started_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            return _row_to_dict(row)

    def _get_total_volume(self) -> float:
        return self._read_float("SELECT COALESCE(SUM(volume), 0) AS value FROM set_logs")

    def _get_total_volume_by_exercise(self, exercise: str) -> float:
        return self._read_float(
            "SELECT COALESCE(SUM(volume), 0) AS value FROM set_logs WHERE exercise = ?",
            (exercise,),
        )

    def _get_pr_by_exercise(self, exercise: str) -> float:
        return self._read_float(
            "SELECT COALESCE(MAX(weight), 0) AS value FROM set_logs WHERE exercise = ?",
            (exercise,),
        )

    def _get_set_count(self) -> int:
        return self._read_int("SELECT COUNT(*) AS value FROM set_logs")

    def _get_set_count_for_workout(self, workout_id: int) -> int:
        return self._read_int("SELECT COUNT(*) AS value FROM set_logs WHERE workout_id = ?", (workout_id,))

    def _get_workout_count(self) -> int:
        return self._read_int("SELECT COUNT(*) AS value FROM workouts")

    def _get_recent_sets(self, limit: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, workout_id, exercise, weight, reps, volume, notes, created_at
                FROM set_logs
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [_row_to_dict(row) for row in rows if row is not None]

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


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert sqlite row to dict and keep None unchanged."""
    if row is None:
        return None
    return dict(row)


def _isoformat(value: datetime) -> str:
    """Return an ISO 8601 UTC timestamp string for sqlite storage."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()
