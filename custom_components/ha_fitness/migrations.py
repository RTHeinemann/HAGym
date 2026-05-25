"""SQLite schema migrations for HA Fitness Tracker."""
from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from .const import LEGACY_USER_ID, LEGACY_USER_NAME

SCHEMA_VERSION = 2


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply all pending schema migrations."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )

    row = conn.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
    current_version = int(row["version"] or 0)

    if current_version < 1:
        _apply_v1(conn)
        current_version = 1

    if current_version < 2:
        _apply_v2(conn)


def _apply_v1(conn: sqlite3.Connection) -> None:
    """Create initial workouts and set logs schema."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS set_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_id INTEGER,
            exercise TEXT NOT NULL,
            weight REAL NOT NULL,
            reps INTEGER NOT NULL,
            volume REAL NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(workout_id) REFERENCES workouts(id)
        );

        CREATE INDEX IF NOT EXISTS idx_set_logs_exercise_created_at
            ON set_logs(exercise, created_at);
        CREATE INDEX IF NOT EXISTS idx_set_logs_created_at
            ON set_logs(created_at);
        CREATE INDEX IF NOT EXISTS idx_set_logs_workout_id
            ON set_logs(workout_id);
        CREATE INDEX IF NOT EXISTS idx_workouts_started_at
            ON workouts(started_at);
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)",
        (1, datetime.now(timezone.utc).isoformat()),
    )


def _apply_v2(conn: sqlite3.Connection) -> None:
    """Add user-aware schema and backfill legacy ownership."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            display_name TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        """
    )

    if not _column_exists(conn, "workouts", "user_id"):
        conn.execute("ALTER TABLE workouts ADD COLUMN user_id TEXT")

    if not _column_exists(conn, "set_logs", "user_id"):
        conn.execute("ALTER TABLE set_logs ADD COLUMN user_id TEXT")

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT OR IGNORE INTO users(id, display_name, enabled, created_at)
        VALUES(?, ?, 1, ?)
        """,
        (LEGACY_USER_ID, LEGACY_USER_NAME, now),
    )

    conn.execute(
        "UPDATE workouts SET user_id = ? WHERE user_id IS NULL",
        (LEGACY_USER_ID,),
    )
    conn.execute(
        "UPDATE set_logs SET user_id = ? WHERE user_id IS NULL",
        (LEGACY_USER_ID,),
    )

    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_workouts_user_id_started_at
            ON workouts(user_id, started_at);
        CREATE INDEX IF NOT EXISTS idx_set_logs_user_id_created_at
            ON set_logs(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_set_logs_user_id_exercise_created_at
            ON set_logs(user_id, exercise, created_at);
        """
    )

    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)",
        (2, now),
    )


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)
