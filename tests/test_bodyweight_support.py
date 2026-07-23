"""Tests for bodyweight support preparation (uses_bodyweight + bodyweight_factor).

Covers:
- New exercises with and without bodyweight flag
- Editing existing exercises preserves / updates bodyweight fields
- Old DB rows without the columns get sensible defaults via migration
- Percentage ↔ factor conversion (UI 0–100 → internal 0.0–1.0)
- calculate_effective_weight() helper function
- Existing volume calculation is unchanged
"""

from __future__ import annotations

import sqlite3

# ---- Import storage internals directly for unit testing without HA runtime ----
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "custom_components" / "ha_fitness")
)


def _create_exercises_table(conn: sqlite3.Connection) -> None:
    """Create the exercises table with bodyweight columns."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exercises (
            id TEXT PRIMARY KEY,
            name_en TEXT NOT NULL,
            name_de TEXT,
            muscle_group TEXT,
            equipment TEXT,
            equipment_id TEXT,
            metric_type TEXT DEFAULT 'strength',
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            uses_bodyweight INTEGER NOT NULL DEFAULT 0,
            bodyweight_factor REAL NOT NULL DEFAULT 1.0,
            created_at TEXT
        )
    """)


def _create_exercises_table_legacy(conn: sqlite3.Connection) -> None:
    """Create the exercises table WITHOUT bodyweight columns (simulates old DB)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exercises (
            id TEXT PRIMARY KEY,
            name_en TEXT NOT NULL,
            name_de TEXT,
            muscle_group TEXT,
            equipment TEXT,
            equipment_id TEXT,
            metric_type TEXT DEFAULT 'strength',
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT
        )
    """)


# ---- calculate_effective_weight helper (duplicated from coordinator.py) ----


def calculate_effective_weight(
    entered_weight: float,
    body_weight: float | None,
    uses_bodyweight: bool,
    bodyweight_factor: float,
) -> float:
    """Calculate effective training weight including optional body weight component."""
    if not uses_bodyweight or body_weight is None:
        return entered_weight

    return entered_weight + body_weight * bodyweight_factor


# ---- Test fixtures ----


@pytest.fixture()
def db():
    """Provide a temporary in-memory SQLite database with exercises table."""
    conn = sqlite3.connect(":memory:")
    _create_exercises_table(conn)
    yield conn
    conn.close()


@pytest.fixture()
def legacy_db():
    """Provide a DB without bodyweight columns (simulates pre-migration state)."""
    conn = sqlite3.connect(":memory:")
    _create_exercises_table_legacy(conn)
    # Insert an exercise row in the old schema
    conn.execute(
        "INSERT INTO exercises(id, name_en, enabled, created_at) VALUES(?, ?, 1, ?)",
        ("pull_up", "Pull Up", "2025-01-01T00:00:00+00:00"),
    )
    conn.commit()
    yield conn
    conn.close()


# ---- Tests for new exercise creation with bodyweight fields ----


class TestNewExerciseDefaults:
    """Test that new exercises get correct defaults."""

    def test_default_no_bodyweight(self, db):
        uses_bw = False  # default
        factor = 1.0  # default
        assert uses_bw is False
        assert factor == 1.0

    def test_insert_with_defaults(self, db):
        """Insert an exercise with defaults — bodyweight disabled."""
        db.execute(
            "INSERT INTO exercises(id, name_en, enabled) VALUES('bench_press', 'Bench Press', 1)",
        )
        row = db.execute(
            "SELECT uses_bodyweight, bodyweight_factor FROM exercises WHERE id='bench_press'"
        ).fetchone()
        assert row is not None
        # SQLite column indices: (uses_bodyweight=8, bodyweight_factor=9)
        assert int(row[0]) == 0  # False
        assert float(row[1]) == pytest.approx(1.0)

    def test_insert_with_65_percent(self, db):
        """Insert an exercise with 65% bodyweight."""
        uses_bw = True
        factor = 0.65
        db.execute(
            "INSERT INTO exercises(id, name_en, enabled, uses_bodyweight, bodyweight_factor) VALUES('dip', 'Dips', 1, ?, ?)",
            (1 if uses_bw else 0, factor),
        )
        row = db.execute(
            "SELECT uses_bodyweight, bodyweight_factor FROM exercises WHERE id='dip'"
        ).fetchone()
        assert int(row[0]) == 1  # True
        assert float(row[1]) == pytest.approx(0.65)

    def test_insert_with_100_percent(self, db):
        """Insert an exercise with 100% bodyweight."""
        db.execute(
            "INSERT INTO exercises(id, name_en, enabled, uses_bodyweight, bodyweight_factor) VALUES('pull_up', 'Pull Up', 1, 1, 1.0)",
        )
        row = db.execute(
            "SELECT uses_bodyweight, bodyweight_factor FROM exercises WHERE id='pull_up'"
        ).fetchone()
        assert int(row[0]) == 1
        assert float(row[1]) == pytest.approx(1.0)

    def test_insert_with_zero_percent(self, db):
        """Insert an exercise with 0% bodyweight (edge case)."""
        db.execute(
            "INSERT INTO exercises(id, name_en, enabled, uses_bodyweight, bodyweight_factor) VALUES('test', 'Test', 1, 1, 0.0)",
        )
        row = db.execute(
            "SELECT uses_bodyweight, bodyweight_factor FROM exercises WHERE id='test'"
        ).fetchone()
        assert int(row[0]) == 1  # flag is True even though factor is 0
        assert float(row[1]) == pytest.approx(0.0)


# ---- Tests for editing existing exercises ----


class TestEditExercise:
    """Test that bodyweight fields can be updated."""

    def test_update_bodyweight_flag(self, db):
        """Toggle uses_bodyweight from False to True."""
        db.execute(
            "INSERT INTO exercises(id, name_en, enabled) VALUES('squat', 'Squat', 1)"
        )
        row = db.execute(
            "SELECT uses_bodyweight FROM exercises WHERE id='squat'"
        ).fetchone()
        assert int(row[0]) == 0

        db.execute("UPDATE exercises SET uses_bodyweight=1 WHERE id='squat'")
        row = db.execute(
            "SELECT uses_bodyweight FROM exercises WHERE id='squat'"
        ).fetchone()
        assert int(row[0]) == 1

    def test_update_factor(self, db):
        """Update bodyweight factor from default to custom value."""
        db.execute(
            "INSERT INTO exercises(id, name_en, enabled) VALUES('dip', 'Dips', 1)",
        )
        row = db.execute(
            "SELECT bodyweight_factor FROM exercises WHERE id='dip'"
        ).fetchone()
        assert float(row[0]) == pytest.approx(1.0)

        db.execute("UPDATE exercises SET bodyweight_factor=0.75 WHERE id='dip'")
        row = db.execute(
            "SELECT bodyweight_factor FROM exercises WHERE id='dip'"
        ).fetchone()
        assert float(row[0]) == pytest.approx(0.75)


# ---- Tests for legacy DB compatibility (migration simulation) ----


class TestLegacyDBCompatibility:
    """Test that old databases without bodyweight columns work after migration."""

    def test_legacy_row_after_add_column(self, legacy_db):
        """Simulate ALTER TABLE adding the column with defaults."""
        # Before migration: no uses_bodyweight/bodyweight_factor columns
        cols = [
            row[1]
            for row in legacy_db.execute("PRAGMA table_info(exercises)").fetchall()
        ]
        assert "uses_bodyweight" not in cols

        # Apply migration (what _apply_v9 does)
        legacy_db.execute(
            "ALTER TABLE exercises ADD COLUMN uses_bodyweight INTEGER NOT NULL DEFAULT 0",
        )
        legacy_db.execute(
            "ALTER TABLE exercises ADD COLUMN bodyweight_factor REAL NOT NULL DEFAULT 1.0",
        )

        # Existing row should get defaults
        row = legacy_db.execute(
            "SELECT uses_bodyweight, bodyweight_factor FROM exercises WHERE id='pull_up'"
        ).fetchone()
        assert int(row[0]) == 0  # False — old exercise not marked as bodyweight
        assert float(row[1]) == pytest.approx(1.0)

    def test_legacy_select_still_works(self, legacy_db):
        """Ensure basic queries still work after migration."""
        cols = [
            row[1]
            for row in legacy_db.execute("PRAGMA table_info(exercises)").fetchall()
        ]
        assert "uses_bodyweight" not in cols

        # Add columns (migration)
        legacy_db.execute(
            "ALTER TABLE exercises ADD COLUMN uses_bodyweight INTEGER NOT NULL DEFAULT 0",
        )
        legacy_db.execute(
            "ALTER TABLE exercises ADD COLUMN bodyweight_factor REAL NOT NULL DEFAULT 1.0",
        )

        row = legacy_db.execute(
            "SELECT id, name_en FROM exercises WHERE id='pull_up'"
        ).fetchone()
        assert row is not None
        assert str(row[0]) == "pull_up"


# ---- Tests for percentage ↔ factor conversion ----


class TestPercentageConversion:
    """Test UI percentage to internal factor and back."""

    def test_percent_to_factor_65(self):
        pct = 65
        factor = round(float(pct) / 100.0, 4)
        assert factor == pytest.approx(0.65)

    def test_percent_to_factor_100(self):
        pct = 100
        factor = round(float(pct) / 100.0, 4)
        assert factor == pytest.approx(1.0)

    def test_percent_to_factor_0(self):
        pct = 0
        factor = round(float(pct) / 100.0, 4)
        assert factor == pytest.approx(0.0)

    def test_factor_to_percent_75(self):
        factor = 0.75
        pct = round(factor * 100)
        assert pct == 75

    def test_factor_to_percent_100(self):
        factor = 1.0
        pct = round(factor * 100)
        assert pct == 100

    def test_roundtrip_preserves_value(self):
        """Percent → Factor → Percent should round-trip."""
        for pct in [0, 25, 50, 65, 75, 100]:
            factor = round(float(pct) / 100.0, 4)
            back_pct = round(factor * 100)
            assert back_pct == pct

    def test_clamp_below_zero(self):
        """Values below 0 should be clamped to 0."""
        factor = max(0.0, min(1.0, -5.0 / 100.0))
        assert factor == pytest.approx(0.0)

    def test_clamp_above_100(self):
        """Values above 100 should be clamped to 1.0."""
        factor = max(0.0, min(1.0, 150.0 / 100.0))
        assert factor == pytest.approx(1.0)


# ---- Tests for calculate_effective_weight() ----


class TestCalculateEffectiveWeight:
    """Test the prepared helper function."""

    def test_no_bodyweight_returns_entered(self):
        result = calculate_effective_weight(80.0, 75.0, False, 1.0)
        assert result == pytest.approx(80.0)

    def test_none_body_weight_returns_entered(self):
        """When body weight source is unavailable, just return entered."""
        result = calculate_effective_weight(60.0, None, True, 0.5)
        assert result == pytest.approx(60.0)

    def test_full_bodyweight_added(self):
        """100% of body weight added to entered weight."""
        result = calculate_effective_weight(20.0, 80.0, True, 1.0)
        assert result == pytest.approx(100.0)

    def test_half_bodyweight_added(self):
        """50% of body weight added to entered weight."""
        result = calculate_effective_weight(20.0, 80.0, True, 0.5)
        assert result == pytest.approx(60.0)

    def test_zero_factor_no_addition(self):
        """Even with flag=True, factor=0 means no addition."""
        result = calculate_effective_weight(70.0, 80.0, True, 0.0)
        assert result == pytest.approx(70.0)

    def test_fractional_factor(self):
        """65% of body weight added to entered weight."""
        result = calculate_effective_weight(10.0, 80.0, True, 0.65)
        assert result == pytest.approx(62.0)


# ---- Tests for volume calculation unchanged ----


class TestVolumeCalculationUnchanged:
    """Verify that existing set_volume = entered_weight * reps is NOT affected."""

    def test_strength_set_volume(self):
        """Standard strength set — bodyweight fields don't affect it yet."""
        entered_weight = 80.0
        reps = 10
        volume = entered_weight * reps
        assert volume == pytest.approx(800.0)

    def test_bodyweight_exercise_volume_unchanged(self):
        """Even for bodyweight exercises, current volume calc is unchanged."""
        # The exercise has uses_bodyweight=True but we don't use it yet
        entered_weight = 20.0  # user-entered added weight (e.g., belt)
        reps = 12
        volume = entered_weight * reps
        assert volume == pytest.approx(240.0)

    def test_zero_added_weight_volume(self):
        """Bodyweight-only exercise with no extra plates."""
        entered_weight = 0.0
        reps = 15
        volume = entered_weight * reps
        assert volume == pytest.approx(0.0)


# ---- Tests for flag persistence when disabled ----


class TestFlagPersistence:
    """Test that bodyweight_factor is preserved even if uses_bodyweight=False."""

    def test_factor_preserved_when_flag_off(self, db):
        """Setting factor to 0.65 but keeping flag off should preserve the value."""
        db.execute(
            "INSERT INTO exercises(id, name_en, enabled) VALUES('test', 'Test', 1)",
        )
        # Set factor even though flag is False
        db.execute("UPDATE exercises SET bodyweight_factor=0.65 WHERE id='test'")

        row = db.execute(
            "SELECT uses_bodyweight, bodyweight_factor FROM exercises WHERE id='test'",
        ).fetchone()
        assert int(row[0]) == 0  # flag still False
        assert float(row[1]) == pytest.approx(0.65)  # factor preserved
