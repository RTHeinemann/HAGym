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
