"""Tests for Layer 1: HA user binding (manage_persons + resolve_user_id).

Covers:
- Migration v10: ha_username column added to users table
- Storage: _upsert_user accepts ha_username and persists it
- Storage: _get_users / _get_user return ha_username
- Coordinator: _get_ha_user looks up user from hass.auth
- Coordinator: resolve_user_id stores HA display_name + username
- Coordinator: list_persons merges hass.auth users with HAGym stats
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure the repo root is on sys.path so `custom_components.ha_fitness` is importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# HA is installed but we mock specific attributes the tests need.
# Import happens here, after sys.path is set.
from custom_components.ha_fitness import migrations
from custom_components.ha_fitness import storage as _storage_mod
from custom_components.ha_fitness import coordinator as _coord_mod


# ---------------------------------------------------------------------------
# Migration v10
# ---------------------------------------------------------------------------

class TestMigrationV10:
    def test_schema_version_is_10(self):
        assert migrations.SCHEMA_VERSION == 10

    def test_v10_adds_ha_username_column(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                display_name TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            INSERT INTO users VALUES ('u1', 'Alice', 1, '2026-01-01');
            CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT);
            INSERT INTO schema_migrations VALUES (9, '2026-01-01');
            """
        )
        migrations.apply_migrations(conn)
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        assert "ha_username" in cols
        ver = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()["v"]
        assert ver == 10
        row = conn.execute("SELECT id, display_name FROM users WHERE id='u1'").fetchone()
        assert row["display_name"] == "Alice"
        conn.close()

    def test_v10_is_idempotent(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                display_name TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                ha_username TEXT
            );
            CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT);
            INSERT INTO schema_migrations VALUES (10, '2026-01-01');
            """
        )
        migrations.apply_migrations(conn)
        conn.close()


# ---------------------------------------------------------------------------
# Storage: _upsert_user / _get_users / _get_user with ha_username
# ---------------------------------------------------------------------------

class TestStorageUserHaUsername:
    def _make_store(self, tmp_path):
        store = _storage_mod.HAFitnessStore(MagicMock())
        db = tmp_path / "test.db"
        store._db_path = str(db)
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                display_name TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                ha_username TEXT
            );
            CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT);
            INSERT INTO schema_migrations VALUES (10, '2026-01-01');
            """
        )
        conn.close()
        return store

    def test_upsert_with_ha_username(self, tmp_path):
        store = self._make_store(tmp_path)
        store._upsert_user("uuid-123", "Alice", "alice")
        row = store._get_user("uuid-123")
        assert row["display_name"] == "Alice"
        assert row["ha_username"] == "alice"

    def test_upsert_preserves_ha_username_on_empty(self, tmp_path):
        store = self._make_store(tmp_path)
        store._upsert_user("uuid-123", "Alice", "alice")
        store._upsert_user("uuid-123", "Alice", "")
        row = store._get_user("uuid-123")
        assert row["ha_username"] == "alice"

    def test_get_users_includes_ha_username(self, tmp_path):
        store = self._make_store(tmp_path)
        store._upsert_user("uuid-1", "Alice", "alice")
        store._upsert_user("uuid-2", "Bob", "bob")
        users = store._get_users()
        assert len(users) == 2
        assert all("ha_username" in u for u in users)


# ---------------------------------------------------------------------------
# Coordinator helpers
# ---------------------------------------------------------------------------

def _make_coordinator(ha_users, hagym_users=None):
    hass = MagicMock()
    hass.data = {"ha_fitness": {"entry-1": None}}
    auth_users = [
        SimpleNamespace(
            id=u["id"],
            name=u["name"],
            username=u.get("username"),
            is_owner=u.get("is_owner", False),
            is_local=u.get("is_local", True),
        )
        for u in ha_users
    ]
    hass.auth.async_get_users = lambda: auth_users

    coord = _coord_mod.HAFitnessCoordinator.__new__(_coord_mod.HAFitnessCoordinator)
    coord.hass = hass
    coord._store = MagicMock()
    coord._store.async_upsert_user = AsyncMock()
    coord._store.async_get_users = AsyncMock(return_value=[])
    coord._store.async_get_set_count = AsyncMock(return_value=0)
    coord._store.async_get_workout_count = AsyncMock(return_value=0)
    coord._current_user_id = None
    coord._selected_user_id = None
    coord._current_workout_user_id = None
    coord._last_saved_set = None
    coord._users = hagym_users or []
    return coord


class TestCoordinatorHaUserLookup:
    def test_get_ha_user_found(self):
        ha_users = [
            {"id": "uuid-123", "name": "Alice", "username": "alice", "is_owner": True},
            {"id": "uuid-456", "name": "Bob", "username": "bob"},
        ]
        coord = _make_coordinator(ha_users)
        user = coord._get_ha_user("uuid-123")
        assert user is not None
        assert user.name == "Alice"
        assert user.username == "alice"

    def test_get_ha_user_not_found(self):
        ha_users = [{"id": "uuid-123", "name": "Alice", "username": "alice"}]
        coord = _make_coordinator(ha_users)
        user = coord._get_ha_user("uuid-999")
        assert user is None

    @pytest.mark.asyncio
    async def test_resolve_user_id_stores_ha_data(self):
        ha_users = [
            {"id": "uuid-123", "name": "Alice Müller", "username": "alice", "is_owner": True},
        ]
        coord = _make_coordinator(ha_users)
        result = await coord.resolve_user_id("uuid-123")
        assert result == "uuid-123"
        coord._store.async_upsert_user.assert_called_once_with(
            "uuid-123", "Alice Müller", "alice"
        )

    @pytest.mark.asyncio
    async def test_resolve_user_id_fallback_unknown_user(self):
        coord = _make_coordinator([])
        result = await coord.resolve_user_id("uuid-999")
        assert result == "uuid-999"
        coord._store.async_upsert_user.assert_called_once_with(
            "uuid-999", "uuid-999", None
        )


class TestListPersons:
    @pytest.mark.asyncio
    async def test_list_persons_merges_auth_and_hagym(self):
        ha_users = [
            {"id": "uuid-123", "name": "Alice", "username": "alice", "is_owner": True},
            {"id": "uuid-456", "name": "Bob", "username": "bob"},
        ]
        hagym_users = [
            {"id": "uuid-123", "display_name": "Alice", "ha_username": "alice",
             "enabled": 1, "created_at": "2026-01-01"},
        ]
        coord = _make_coordinator(ha_users, hagym_users)
        persons = await coord.list_persons()
        assert len(persons) == 2
        alice = next(p for p in persons if p["id"] == "uuid-123")
        bob = next(p for p in persons if p["id"] == "uuid-456")
        assert alice["in_hagym"] is True
        assert bob["in_hagym"] is False
        assert alice["display_name"] == "Alice"
        assert alice["username"] == "alice"
        assert alice["is_owner"] is True

    @pytest.mark.asyncio
    async def test_list_persons_with_stats(self):
        ha_users = [
            {"id": "uuid-123", "name": "Alice", "username": "alice"},
        ]
        hagym_users = [
            {"id": "uuid-123", "display_name": "Alice", "ha_username": "alice",
             "enabled": 1, "created_at": "2026-01-01"},
        ]
        coord = _make_coordinator(ha_users, hagym_users)
        coord._store.async_get_set_count = AsyncMock(return_value=42)
        coord._store.async_get_workout_count = AsyncMock(return_value=7)
        persons = await coord.list_persons()
        assert persons[0]["set_count"] == 42
        assert persons[0]["workout_count"] == 7

    @pytest.mark.asyncio
    async def test_list_persons_auth_failure_returns_empty(self):
        hass = MagicMock()
        hass.auth.async_get_users = MagicMock(side_effect=Exception("auth error"))
        coordinator = _coord_mod.HAFitnessCoordinator.__new__(_coord_mod.HAFitnessCoordinator)
        coordinator.hass = hass
        coordinator._store = MagicMock()
        coordinator._store.async_get_set_count = AsyncMock(return_value=0)
        coordinator._store.async_get_workout_count = AsyncMock(return_value=0)
        coordinator._users = []
        persons = await coordinator.list_persons()
        assert persons == []


# ---------------------------------------------------------------------------
# Coordinator: async_get_user_statistics (per-user isolation)
# ---------------------------------------------------------------------------

class TestGetUserStatistics:
    def _make_coord(self, ha_users=None):
        hass = MagicMock()
        hass.config.time_zone = "Europe/Berlin"
        hass.data = {"ha_fitness": {"entry-1": None}}
        coord = _coord_mod.HAFitnessCoordinator.__new__(_coord_mod.HAFitnessCoordinator)
        coord.hass = hass
        coord._store = MagicMock()
        coord._store.async_get_total_volume = AsyncMock(return_value=1234.5)
        coord._store.async_get_set_count = AsyncMock(return_value=42)
        coord._store.async_get_workout_count = AsyncMock(return_value=7)
        coord._store.async_get_recent_sets = AsyncMock(return_value=[{"id": 1}])
        coord._store.async_get_exercise_statistics = AsyncMock(return_value=[{"exercise_id": "bench", "total_volume": 800.0}])
        coord._store.async_get_muscle_group_statistics = AsyncMock(return_value=[{"muscle_group_id": "chest", "total_volume": 600.0}])
        coord._store.async_get_weekly_summary = AsyncMock(return_value={"total_volume": 500.0, "active_days": 2})
        return coord

    @pytest.mark.asyncio
    async def test_returns_all_stats_for_user(self):
        coord = self._make_coord()
        stats = await coord.async_get_user_statistics("uuid-felicitas")
        assert stats["user_id"] == "uuid-felicitas"
        assert stats["total_volume"] == 1234.5
        assert stats["total_sets"] == 42
        assert stats["workout_count"] == 7
        assert stats["recent_sets"] == [{"id": 1}]
        assert len(stats["exercise_statistics"]) == 1
        assert len(stats["muscle_group_statistics"]) == 1
        assert stats["weekly_summary"]["total_volume"] == 500.0

    @pytest.mark.asyncio
    async def test_user_id_passed_to_all_storage_calls(self):
        coord = self._make_coord()
        await coord.async_get_user_statistics("uuid-aaron")
        # Verify user_id was passed to each storage method
        coord._store.async_get_total_volume.assert_called_once_with("uuid-aaron")
        coord._store.async_get_set_count.assert_called_once_with("uuid-aaron")
        coord._store.async_get_workout_count.assert_called_once_with("uuid-aaron")
        coord._store.async_get_recent_sets.assert_called_once_with(10, "uuid-aaron")
        coord._store.async_get_exercise_statistics.assert_called_once_with(user_id="uuid-aaron")
        coord._store.async_get_muscle_group_statistics.assert_called_once_with(user_id="uuid-aaron")
        # weekly summary called with user_id kwarg
        coord._store.async_get_weekly_summary.assert_called_once()
        call = coord._store.async_get_weekly_summary.call_args
        assert call.kwargs.get("user_id") == "uuid-aaron"


# ---------------------------------------------------------------------------
# Per-user sensor entities
# ---------------------------------------------------------------------------

class TestPerUserSensor:
    def _setup(self):
        coord = MagicMock()
        coord.display_name = "Test"
        coord.list_persons = MagicMock(return_value=[
            {"id": "uuid-felicitas", "name": "Felicitas", "username": "felicitas", "in_hagym": True, "set_count": 42, "workout_count": 7},
            {"id": "uuid-empty", "name": "Empty", "username": "empty", "in_hagym": False, "set_count": 0, "workout_count": 0},
        ])
        coord.async_get_user_statistics = AsyncMock(return_value={
            "user_id": "uuid-felicitas",
            "total_volume": 999.0,
            "total_sets": 33,
            "workout_count": 5,
            "recent_sets": [],
            "exercise_statistics": [],
            "muscle_group_statistics": [],
            "weekly_summary": {"total_volume": 100.0, "total_sets": 8},
        })
        entry = MagicMock()
        entry.entry_id = "entry-1"
        return coord, entry

    def test_build_per_user_entities(self):
        from custom_components.ha_fitness.sensor import _build_per_user_entities, _PER_USER_METRICS
        coord, entry = self._setup()
        user = {"id": "uuid-felicitas", "name": "Felicitas", "in_hagym": True}
        entities = _build_per_user_entities(coord, entry, user)
        assert len(entities) == len(_PER_USER_METRICS)
        for ent in entities:
            assert ent._attr_unique_id.startswith("entry-1_user_uuid-felicitas_")
            assert ent._user_id == "uuid-felicitas"

    def test_unique_id_is_stable(self):
        from custom_components.ha_fitness.sensor import _build_per_user_entities
        coord, entry = self._setup()
        user = {"id": "uuid-aaron", "name": "Aaron", "in_hagym": True}
        e1 = _build_per_user_entities(coord, entry, user)
        e2 = _build_per_user_entities(coord, entry, user)
        assert [e._attr_unique_id for e in e1] == [e._attr_unique_id for e in e2]

    @pytest.mark.asyncio
    async def test_native_value_reads_coordinator_cache(self):
        from custom_components.ha_fitness.sensor import _build_per_user_entities
        coord, entry = self._setup()
        # Simulate coordinator having populated _user_statistics during refresh
        coord._user_statistics = {
            "uuid-felicitas": {
                "total_volume": 999.0,
                "total_sets": 33,
                "workout_count": 5,
                "weekly_volume": 100.0,
                "weekly_sets": 8,
            }
        }
        user = {"id": "uuid-felicitas", "name": "Felicitas", "in_hagym": True}
        entities = _build_per_user_entities(coord, entry, user)
        vol_sensor = [e for e in entities if e._metric_key == "total_volume"][0]
        assert vol_sensor.native_value == 999.0
        sets_sensor = [e for e in entities if e._metric_key == "total_sets"][0]
        assert sets_sensor.native_value == 33
        weekly_sensor = [e for e in entities if e._metric_key == "weekly_volume"][0]
        assert weekly_sensor.native_value == 100.0

    def test_native_value_returns_defaults_when_user_not_in_cache(self):
        from custom_components.ha_fitness.sensor import _build_per_user_entities
        coord, entry = self._setup()
        coord._user_statistics = {}  # empty — user not yet refreshed
        user = {"id": "uuid-unknown", "name": "Unknown", "in_hagym": True}
        entities = _build_per_user_entities(coord, entry, user)
        vol_sensor = [e for e in entities if e._metric_key == "total_volume"][0]
        assert vol_sensor.native_value == 0.0
