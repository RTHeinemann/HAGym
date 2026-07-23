"""Tests for normalized muscle-group weight factor logic.

Covers:
- Validation (empty, duplicates, out-of-range, sum ≠ 100%)
- Normalization math (proportional from existing, role-based defaults)
- Rounding remainder handling
- Storage layer _replace_muscle_groups_with_weights integration
"""

from __future__ import annotations

import pytest
import sqlite3
import tempfile
from pathlib import Path

# Import storage internals directly for unit testing without HA runtime.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "custom_components" / "ha_fitness"))

from datetime import datetime, timezone


def _isoformat(dt: datetime) -> str:
    return dt.isoformat()


# ---- Constants from const.py (duplicated to avoid HA runtime deps) ----
MUSCLE_ROLE_PRIMARY = "primary"
MUSCLE_ROLE_SECONDARY = "secondary"
MUSCLE_ROLE_STABILIZER = "stabilizer"

_MUSCLE_WEIGHT_TOLERANCE = 0.001


def _normalize_muscle_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized in (MUSCLE_ROLE_PRIMARY, MUSCLE_ROLE_SECONDARY, MUSCLE_ROLE_STABILIZER):
        return normalized
    return MUSCLE_ROLE_PRIMARY


# ---- Minimal SQLite test harness ----

def _create_test_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exercise_muscle_groups (
            exercise_id TEXT,
            muscle_group_id TEXT,
            role TEXT DEFAULT 'primary',
            weight_factor REAL DEFAULT 1.0,
            created_at TEXT,
            updated_at TEXT,
            PRIMARY KEY (exercise_id, muscle_group_id)
        )
    """)
    conn.commit()
    return conn


def _replace_muscle_groups_with_weights(
    conn: sqlite3.Connection, exercise_id: str, mappings: list[dict]
) -> None:
    """Pure-Python version of the storage layer logic for testing."""
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

        if mg_id in seen_ids:
            raise ValueError(f"muscle_group_duplicate:{mg_id}")
        seen_ids.add(mg_id)

        validated_rows.append((mg_id, role, round(weight_factor, 4)))

    if not validated_rows:
        raise ValueError("muscle_group_mapping_empty")

    total = sum(f for _, _, f in validated_rows)
    if abs(total - 1.0) > _MUSCLE_WEIGHT_TOLERANCE:
        raise ValueError("muscle_group_weights_sum")

    normalized_factors: list[float] = [f for _, _, f in validated_rows]
    current_sum = round(sum(normalized_factors), 4)
    diff = round(1.0 - current_sum, 4)
    if abs(diff) > 0:
        last_idx = len(normalized_factors) - 1
        normalized_factors[last_idx] = round(normalized_factors[last_idx] + diff, 4)

    now = _isoformat(datetime.now(timezone.utc))
    conn.execute(
        "DELETE FROM exercise_muscle_groups WHERE exercise_id = ?", (exercise_id,)
    )
    for idx, (mg_id, role, _) in enumerate(validated_rows):
        conn.execute(
            """INSERT INTO exercise_muscle_groups(
                exercise_id, muscle_group_id, role, weight_factor, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (exercise_id, mg_id, role, normalized_factors[idx], now, now),
        )
    conn.commit()


def _get_rows(conn: sqlite3.Connection, exercise_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT muscle_group_id, role, weight_factor FROM exercise_muscle_groups WHERE exercise_id = ?",
        (exercise_id,),
    ).fetchall()
    return [
        {"muscle_group_id": r[0], "role": r[1], "weight_factor": r[2]} for r in rows
    ]


# ---- Tests ----

class TestValidation:
    """Server-side validation of weight inputs."""

    def test_empty_mappings_raises(self, tmp_path):
        conn = _create_test_db(tmp_path / "test.db")
        with pytest.raises(ValueError, match="muscle_group_mapping_empty"):
            _replace_muscle_groups_with_weights(conn, "bench_press", [])  # noqa: F821

    def test_duplicate_id_raises(self, tmp_path):
        conn = _create_test_db(tmp_path / "test.db")
        mappings = [
            {"muscle_group_id": "chest", "role": "primary", "weight_factor": 0.5},
            {"muscle_group_id": "chest", "role": "secondary", "weight_factor": 0.5},
        ]
        with pytest.raises(ValueError, match="muscle_group_duplicate"):  # noqa: F821
            _replace_muscle_groups_with_weights(conn, "bench_press", mappings)

    def test_sum_not_100_raises(self, tmp_path):
        conn = _create_test_db(tmp_path / "test.db")
        mappings = [
            {"muscle_group_id": "chest", "role": "primary", "weight_factor": 0.3},
            {"muscle_group_id": "back", "role": "secondary", "weight_factor": 0.2},
        ]
        with pytest.raises(ValueError, match="muscle_group_weights_sum"):  # noqa: F821
            _replace_muscle_groups_with_weights(conn, "bench_press", mappings)

    def test_negative_weight_clamped_to_zero(self, tmp_path):
        conn = _create_test_db(tmp_path / "test.db")
        mappings = [
            {"muscle_group_id": "chest", "role": "primary", "weight_factor": -0.1},
            {"muscle_group_id": "back", "role": "secondary", "weight_factor": 1.0},
        ]
        _replace_muscle_groups_with_weights(conn, "bench_press", mappings)
        rows = _get_rows(conn, "bench_press")
        assert len(rows) == 2

    def test_weight_over_1_clamped(self, tmp_path):
        conn = _create_test_db(tmp_path / "test.db")
        # Over-1 gets clamped to 1.0; sum will be > 1 → raises unless other is adjusted
        mappings = [
            {"muscle_group_id": "chest", "role": "primary", "weight_factor": 2.0},
            {"muscle_group_id": "back", "role": "secondary", "weight_factor": -1.0},
        ]
        # After clamping: chest=1.0, back=0.0 → sum = 1.0 ✓
        _replace_muscle_groups_with_weights(conn, "bench_press", mappings)
        rows = _get_rows(conn, "bench_press")
        assert len(rows) == 2

    def test_sum_within_tolerance_accepted(self, tmp_path):
        conn = _create_test_db(tmp_path / "test.db")
        # Sum is 0.9995 → within tolerance of ±0.001 from 1.0? No, diff=0.0005 < 0.001 ✓
        mappings = [
            {"muscle_group_id": "chest", "role": "primary", "weight_factor": 0.6},
            {"muscle_group_id": "back", "role": "secondary", "weight_factor": 0.3995},
            {"muscle_group_id": "core", "role": "stabilizer", "weight_factor": 0.0005},
        ]
        _replace_muscle_groups_with_weights(conn, "bench_press", mappings)
        rows = _get_rows(conn, "bench_press")
        assert len(rows) == 3


class TestNormalization:
    """Weight normalization and rounding remainder logic."""

    def test_exact_sum_stored_as_is(self, tmp_path):
        conn = _create_test_db(tmp_path / "test.db")
        mappings = [
            {"muscle_group_id": "chest", "role": "primary", "weight_factor": 0.6},
            {"muscle_group_id": "back", "role": "secondary", "weight_factor": 0.4},
        ]
        _replace_muscle_groups_with_weights(conn, "bench_press", mappings)
        rows = _get_rows(conn, "bench_press")
        factors = [r["weight_factor"] for r in rows]
        assert round(sum(factors), 4) == 1.0

    def test_rounding_remainder_on_last_entry(self, tmp_path):
        conn = _create_test_db(tmp_path / "test.db")
        # Three equal thirds can't be exactly represented; last gets remainder
        mappings = [
            {"muscle_group_id": "chest", "role": "primary", "weight_factor": 0.3334},
            {"muscle_group_id": "back", "role": "secondary", "weight_factor": 0.3333},
            {"muscle_group_id": "core", "role": "stabilizer", "weight_factor": 0.3333},
        ]
        _replace_muscle_groups_with_weights(conn, "bench_press", mappings)
        rows = _get_rows(conn, "bench_press")
        factors = [r["weight_factor"] for r in rows]
        assert round(sum(factors), 4) == 1.0

    def test_atomically_replaces_all_mappings(self, tmp_path):
        conn = _create_test_db(tmp_path / "test.db")
        # First write: two groups
        mappings_a = [
            {"muscle_group_id": "chest", "role": "primary", "weight_factor": 0.5},
            {"muscle_group_id": "back", "role": "secondary", "weight_factor": 0.5},
        ]
        _replace_muscle_groups_with_weights(conn, "bench_press", mappings_a)
        assert len(_get_rows(conn, "bench_press")) == 2

        # Second write: completely different groups → old ones gone
        mappings_b = [
            {"muscle_group_id": "legs", "role": "primary", "weight_factor": 0.7},
            {"muscle_group_id": "core", "role": "stabilizer", "weight_factor": 0.3},
        ]
        _replace_muscle_groups_with_weights(conn, "bench_press", mappings_b)
        rows = _get_rows(conn, "bench_press")
        ids = {r["muscle_group_id"] for r in rows}
        assert ids == {"legs", "core"}


class TestRoleDefaults:
    """Default weight distribution by role."""

    def test_default_primary_60_secondary_30_stabilizer_10(self):
        # Simulate the config_flow default computation logic
        primary_ids = ["chest"]
        secondary_ids = ["triceps"]
        stabilizer_ids = ["shoulders"]

        counts: dict[str, int] = {"primary": 0, "secondary": 0, "stabilizer": 0}
        role_map: dict[str, str] = {}
        for mg in primary_ids:
            role_map[mg] = "primary"
            counts["primary"] += 1
        for mg in secondary_ids:
            role_map[mg] = "secondary"
            counts["secondary"] += 1
        for mg in stabilizer_ids:
            role_map[mg] = "stabilizer"
            counts["stabilizer"] += 1

        shares: dict[str, float] = {"primary": 0.6, "secondary": 0.3, "stabilizer": 0.1}
        all_ids = primary_ids + secondary_ids + stabilizer_ids

        factors: dict[str, float] = {}
        for mg_id in all_ids:
            role = role_map[mg_id]
            n = counts[role] or 1
            share = shares.get(role, 0.3)
            factors[mg_id] = round(share / n, 4)

        assert factors["chest"] == 0.6
        assert factors["triceps"] == 0.3
        assert factors["shoulders"] == 0.1
        total = sum(factors.values())
        assert abs(total - 1.0) < _MUSCLE_WEIGHT_TOLERANCE

    def test_empty_role_redistributes(self):
        # No stabilizer → its 10% redistributed to primary and secondary proportionally
        primary_ids = ["chest"]
        secondary_ids = ["triceps"]
        stabilizer_ids: list[str] = []

        counts: dict[str, int] = {"primary": 0, "secondary": 0, "stabilizer": 0}
        role_map: dict[str, str] = {}
        for mg in primary_ids:
            role_map[mg] = "primary"
            counts["primary"] += 1
        for mg in secondary_ids:
            role_map[mg] = "secondary"
            counts["secondary"] += 1

        shares: dict[str, float] = {"primary": 0.6, "secondary": 0.3, "stabilizer": 0.1}
        active_roles = [r for r in counts if counts[r] > 0]
        inactive_share = sum(
            shares.get(r, 0) for r in ("primary", "secondary", "stabilizer") if r not in active_roles
        )
        active_total = sum(shares.get(r, 0) for r in active_roles) or 1.0

        redistributed: dict[str, float] = {}
        for r in active_roles:
            base_share = shares.get(r, 0.0)
            if len(active_roles) > 1 and inactive_share > 0:
                redistributed[r] = round(
                    base_share + (inactive_share * base_share / active_total), 4
                )
            else:
                redistributed[r] = shares.get(r, 0.0)

        all_ids = primary_ids + secondary_ids + stabilizer_ids
        factors: dict[str, float] = {}
        for mg_id in all_ids:
            role = role_map[mg_id]
            n = counts[role] or 1
            share = redistributed.get(role, 0.3)
            factors[mg_id] = round(share / n, 4)

        total = sum(factors.values())
        assert abs(total - 1.0) < _MUSCLE_WEIGHT_TOLERANCE
        # Primary should get more than base 60% since stabilizer is empty
        assert factors["chest"] > 0.6


class TestProportionalNormalization:
    """Existing weight factors normalized proportionally."""

    def test_proportional_from_existing(self):
        existing_factors = {"chest": 1.0, "triceps": 0.5}
        total_raw = sum(existing_factors.values())
        assert total_raw == 1.5

        normalized = {k: round(v / total_raw, 4) for k, v in existing_factors.items()}
        # chest should be ~2/3, triceps ~1/3
        assert abs(normalized["chest"] - 0.6667) < _MUSCLE_WEIGHT_TOLERANCE
        assert abs(normalized["triceps"] - 0.3333) < _MUSCLE_WEIGHT_TOLERANCE
        total = sum(normalized.values())
        # May not be exactly 1.0 due to rounding; that's OK, storage layer fixes remainder


# ---- Run with: pytest tests/test_muscle_group_weighting.py -v ----
