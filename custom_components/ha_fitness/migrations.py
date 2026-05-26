"""SQLite schema migrations for HAGym."""
from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from .const import (
    DEFAULT_EQUIPMENT,
    DEFAULT_EXERCISE_MUSCLE_GROUP_MAP,
    DEFAULT_EXERCISE_EQUIPMENT_MAP,
    DEFAULT_EXERCISES,
    DEFAULT_MUSCLE_GROUPS,
    LEGACY_USER_ID,
    LEGACY_USER_NAME,
)

SCHEMA_VERSION = 5


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
        current_version = 2

    if current_version < 3:
        _apply_v3(conn)
        current_version = 3

    if current_version < 4:
        _apply_v4(conn)
        current_version = 4

    if current_version < 5:
        _apply_v5(conn)


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


def _apply_v3(conn: sqlite3.Connection) -> None:
    """Add exercises catalog and set_logs.exercise_id with backfill."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS exercises (
            id TEXT PRIMARY KEY,
            name_en TEXT NOT NULL,
            name_de TEXT,
            muscle_group TEXT,
            equipment TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        """
    )

    if not _column_exists(conn, "set_logs", "exercise_id"):
        conn.execute("ALTER TABLE set_logs ADD COLUMN exercise_id TEXT")

    now = datetime.now(timezone.utc).isoformat()
    for exercise in DEFAULT_EXERCISES:
        conn.execute(
            """
            INSERT INTO exercises(id, name_en, name_de, muscle_group, equipment, enabled, sort_order, created_at)
            VALUES(?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name_en = excluded.name_en,
                name_de = excluded.name_de,
                muscle_group = excluded.muscle_group,
                equipment = COALESCE(exercises.equipment, excluded.equipment),
                enabled = 1,
                sort_order = excluded.sort_order
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

    conn.execute(
        """
        UPDATE set_logs
        SET exercise_id = CASE lower(trim(exercise))
            WHEN 'bench press' THEN 'bench_press'
            WHEN 'bankdrücken' THEN 'bench_press'
            WHEN 'bench_press' THEN 'bench_press'
            WHEN 'squat' THEN 'squat'
            WHEN 'kniebeuge' THEN 'squat'
            WHEN 'deadlift' THEN 'deadlift'
            WHEN 'kreuzheben' THEN 'deadlift'
            WHEN 'shoulder press' THEN 'shoulder_press'
            WHEN 'schulterdrücken' THEN 'shoulder_press'
            WHEN 'shoulder_press' THEN 'shoulder_press'
            WHEN 'row' THEN 'row'
            WHEN 'rudern' THEN 'row'
            WHEN 'lat pulldown' THEN 'lat_pulldown'
            WHEN 'lat_pulldown' THEN 'lat_pulldown'
            WHEN 'latzug' THEN 'lat_pulldown'
            WHEN 'bicep curl' THEN 'bicep_curl'
            WHEN 'bizepscurls' THEN 'bicep_curl'
            WHEN 'bicep_curl' THEN 'bicep_curl'
            WHEN 'tricep pushdown' THEN 'tricep_pushdown'
            WHEN 'trizepsdrücken' THEN 'tricep_pushdown'
            WHEN 'tricep_pushdown' THEN 'tricep_pushdown'
            ELSE exercise_id
        END
        WHERE exercise_id IS NULL
        """
    )

    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_set_logs_exercise_id_created_at
            ON set_logs(exercise_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_set_logs_user_id_exercise_id_created_at
            ON set_logs(user_id, exercise_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_exercises_enabled_sort_order
            ON exercises(enabled, sort_order, name_en);
        """
    )

    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)",
        (3, now),
    )


def _apply_v4(conn: sqlite3.Connection) -> None:
    """Add equipment catalog and equipment relations for exercises/set logs."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS equipment (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            icon TEXT,
            location TEXT,
            enabled INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 100,
            created_at TEXT NOT NULL
        );
        """
    )

    if not _column_exists(conn, "exercises", "equipment_id"):
        conn.execute("ALTER TABLE exercises ADD COLUMN equipment_id TEXT")

    if not _column_exists(conn, "set_logs", "equipment_id"):
        conn.execute("ALTER TABLE set_logs ADD COLUMN equipment_id TEXT")

    now = datetime.now(timezone.utc).isoformat()
    for item in DEFAULT_EQUIPMENT:
        conn.execute(
            """
            INSERT INTO equipment(id, name, description, icon, location, enabled, sort_order, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = COALESCE(equipment.description, excluded.description),
                icon = COALESCE(equipment.icon, excluded.icon),
                location = COALESCE(equipment.location, excluded.location),
                enabled = COALESCE(equipment.enabled, excluded.enabled),
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

    for exercise_id, equipment_id in DEFAULT_EXERCISE_EQUIPMENT_MAP.items():
        conn.execute(
            """
            UPDATE exercises
            SET equipment_id = ?
            WHERE id = ?
              AND (equipment_id IS NULL OR TRIM(equipment_id) = '')
            """,
            (equipment_id, exercise_id),
        )

    conn.execute(
        """
        UPDATE set_logs
        SET equipment_id = (
            SELECT e.equipment_id
            FROM exercises e
            WHERE e.id = set_logs.exercise_id
            LIMIT 1
        )
        WHERE (equipment_id IS NULL OR TRIM(equipment_id) = '')
          AND exercise_id IS NOT NULL
        """
    )

    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_equipment_enabled_sort_order
            ON equipment(enabled, sort_order, name);
        CREATE INDEX IF NOT EXISTS idx_exercises_equipment_id
            ON exercises(equipment_id);
        CREATE INDEX IF NOT EXISTS idx_set_logs_equipment_id_created_at
            ON set_logs(equipment_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_set_logs_user_id_equipment_id_created_at
            ON set_logs(user_id, equipment_id, created_at);
        """
    )

    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)",
        (4, now),
    )


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    pragma_sql_by_table = {
        "workouts": "PRAGMA table_info(workouts)",
        "set_logs": "PRAGMA table_info(set_logs)",
        "exercises": "PRAGMA table_info(exercises)",
        "equipment": "PRAGMA table_info(equipment)",
        "muscle_groups": "PRAGMA table_info(muscle_groups)",
        "exercise_muscle_groups": "PRAGMA table_info(exercise_muscle_groups)",
    }
    pragma_sql = pragma_sql_by_table.get(table)
    if pragma_sql is None:
        raise ValueError(f"Unsupported table for schema inspection: {table}")
    rows = conn.execute(pragma_sql).fetchall()
    return any(row["name"] == column for row in rows)


def _apply_v5(conn: sqlite3.Connection) -> None:
    """Add muscle group catalog and exercise-to-muscle mapping relations."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS muscle_groups (
            id TEXT PRIMARY KEY,
            name_en TEXT NOT NULL,
            name_de TEXT,
            description TEXT,
            icon TEXT,
            body_region TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 100,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS exercise_muscle_groups (
            exercise_id TEXT NOT NULL,
            muscle_group_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'primary',
            weight_factor REAL NOT NULL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (exercise_id, muscle_group_id)
        );
        """
    )

    now = datetime.now(timezone.utc).isoformat()

    for group in DEFAULT_MUSCLE_GROUPS:
        conn.execute(
            """
            INSERT INTO muscle_groups(
                id, name_en, name_de, description, icon, body_region, enabled, sort_order, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (
                str(group["id"]),
                str(group["name_en"]),
                group.get("name_de"),
                group.get("description"),
                group.get("icon"),
                group.get("body_region"),
                1 if bool(group.get("enabled", True)) else 0,
                int(group.get("sort_order", 100)),
                now,
                now,
            ),
        )

    for exercise_id, mappings in DEFAULT_EXERCISE_MUSCLE_GROUP_MAP.items():
        for mapping in mappings:
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
                    str(mapping.get("role") or "primary"),
                    float(mapping.get("weight_factor", 1.0)),
                    now,
                    now,
                ),
            )

    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_muscle_groups_enabled_sort_order
            ON muscle_groups(enabled, sort_order, name_en);
        CREATE INDEX IF NOT EXISTS idx_exercise_muscle_groups_exercise_id
            ON exercise_muscle_groups(exercise_id);
        CREATE INDEX IF NOT EXISTS idx_exercise_muscle_groups_muscle_group_id
            ON exercise_muscle_groups(muscle_group_id);
        """
    )

    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)",
        (5, now),
    )
