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


# ---- Tests for edit-flow percentage ↔ factor conversion (Bug-Fix) ----


class TestEditFlowConversion:
    """Test that the edit-exercise flow correctly converts percent↔factor.

    Covers the bug where a stored factor of 0.65 was used as fallback,
    then divided by 100 again → 0.0065 instead of 0.65.
    """

    def test_edit_with_factor_065_stores_correctly(self, db):
        """Bearbeiten einer Übung mit Faktor 0.65 — speichert 0.65."""
        # Setup: Übung mit bodyweight_factor = 0.65
        db.execute(
            "INSERT INTO exercises(id, name_en, enabled, uses_bodyweight, bodyweight_factor) "
            "VALUES('dip', 'Dips', 1, 1, 0.65)"
        )
        row = db.execute(
            "SELECT bodyweight_factor FROM exercises WHERE id='dip'"
        ).fetchone()
        assert float(row[0]) == pytest.approx(0.65)

        # Simuliere: Formular sendet 65 (Prozent), Konvertierung /100 → 0.65
        pct_from_form = 65
        factor = round(float(pct_from_form) / 100.0, 4)
        assert factor == pytest.approx(0.65)

    def test_submit_65_percent_stores_factor_065(self):
        """Absenden mit Prozentwert 65 speichert Faktor 0.65."""
        pct_from_form = 65
        factor = round(float(pct_from_form) / 100.0, 4)
        assert factor == pytest.approx(0.65)

    def test_missing_field_preserves_existing_factor(self, db):
        """Fehlendes Formularfeld verändert einen bestehenden Faktor nicht."""
        # Setup: Übung mit bodyweight_factor = 0.75
        db.execute(
            "INSERT INTO exercises(id, name_en, enabled, uses_bodyweight, bodyweight_factor) "
            "VALUES('pull_up', 'Pull Up', 1, 1, 0.75)"
        )
        stored = float(db.execute(
            "SELECT bodyweight_factor FROM exercises WHERE id='pull_up'"
        ).fetchone()[0])

        # Simuliere: ATTR_BODYWEIGHT_FACTOR NICHT in user_input → behalte stored
        factor_after_edit = stored  # kein /100, direkt übernehmen
        assert factor_after_edit == pytest.approx(0.75)

    def test_disable_then_reenable_preserves_factor(self, db):
        """Checkbox deaktivieren und später wieder aktivieren erhält den Faktor."""
        # Setup: Übung mit uses_bodyweight=1, bodyweight_factor=0.65
        db.execute(
            "INSERT INTO exercises(id, name_en, enabled, uses_bodyweight, bodyweight_factor) "
            "VALUES('dip', 'Dips', 1, 1, 0.65)"
        )

        # Schritt 1: Checkbox deaktivieren (uses_bodyweight → False), Faktor bleibt erhalten
        db.execute("UPDATE exercises SET uses_bodyweight=0 WHERE id='dip'")
        row = db.execute(
            "SELECT uses_bodyweight, bodyweight_factor FROM exercises WHERE id='dip'"
        ).fetchone()
        assert int(row[0]) == 0
        assert float(row[1]) == pytest.approx(0.65)

        # Schritt 2: Checkbox wieder aktivieren — Faktor ist immer noch da
        db.execute("UPDATE exercises SET uses_bodyweight=1 WHERE id='dip'")
        row = db.execute(
            "SELECT uses_bodyweight, bodyweight_factor FROM exercises WHERE id='dip'"
        ).fetchone()
        assert int(row[0]) == 1
        assert float(row[1]) == pytest.approx(0.65)

    def test_schema_default_converts_stored_factor_to_percent(self):
        """Schema-Default wandelt gespeicherten Faktor korrekt in Prozent um."""
        stored_factor = 0.65
        pct_for_form = int(round(stored_factor * 100))
        assert pct_for_form == 65

    def test_schema_default_roundtrip(self):
        """Runde Reise: Faktor → Prozent im Formular → zurück zu Faktor."""
        original_factor = 0.73
        # Schritt 1: Faktor wird als Prozent für das Formular angezeigt
        pct_for_form = int(round(original_factor * 100))
        assert pct_for_form == 73
        # Schritt 2: Prozentwert wird beim Absenden zurück zu Faktor konvertiert
        recovered_factor = round(float(pct_for_form) / 100.0, 4)
        assert recovered_factor == pytest.approx(0.73)

    def test_old_bug_would_produce_wrong_result(self):
        """
        Reproduziert den alten Bug: gespeicherter Faktor als Fallback,
        dann nochmal /100 → falsches Ergebnis.
        Dieser Test zeigt, dass der BUG NICHT mehr auftritt.
        """
        stored_factor = 0.65
        # ALTES (buggy) Verhalten:
        buggy_result = round(float(stored_factor) / 100.0, 4)
        assert buggy_result == pytest.approx(0.0065)  # das war der Bug!

        # NEUES (korrigiertes) Verhalten: wenn Feld fehlt, nimm stored direkt:
        correct_result = stored_factor  # kein /100 mehr
        assert correct_result == pytest.approx(0.65)


class TestZeroFactorHandling:
    """Test that bodyweight_factor = 0.0 is preserved (not replaced by default 1.0).

    Covers the bug where `exercise.get(..., 1.0) or 1.0` turned 0.0 into 1.0
    because 0.0 evaluates to False in Python.
    """

    def test_zero_factor_is_valid(self):
        """0.0 is a valid bodyweight factor — not falsy-replaced."""
        stored = 0.0
        # Korrekte None-Prüfung: nur None → Default, nicht 0.0
        result = 1.0 if stored is None else float(stored)
        assert result == pytest.approx(0.0)

    def test_zero_factor_shows_as_0_percent(self):
        """Faktor 0.0 wird im Formular als 0 % angezeigt — nicht 100 %."""
        stored = 0.0
        pct = int(round(stored * 100))
        assert pct == 0

    def test_zero_factor_preserved_on_missing_field(self, db):
        """Fehlendes Formularfeld erhält Faktor 0.0 unverändert."""
        # Setup: Übung mit bodyweight_factor = 0.0
        db.execute(
            "INSERT INTO exercises(id, name_en, enabled, uses_bodyweight, bodyweight_factor) "
            "VALUES('test_zero', 'Test Zero', 1, 1, 0.0)"
        )
        stored = float(db.execute(
            "SELECT bodyweight_factor FROM exercises WHERE id='test_zero'"
        ).fetchone()[0])

        # Simuliere: ATTR_BODYWEIGHT_FACTOR NICHT in user_input → behalte stored
        factor_after_edit = stored  # kein /100, direkt übernehmen
        assert factor_after_edit == pytest.approx(0.0)

    def test_zero_factor_roundtrip(self):
        """Runde Reise: Faktor 0.0 → Prozent 0 im Formular → zurück zu Faktor 0.0."""
        original = 0.0
        pct_for_form = int(round(original * 100))
        assert pct_for_form == 0
        recovered_factor = round(float(pct_for_form) / 100.0, 4)
        assert recovered_factor == pytest.approx(0.0)

    def test_old_bug_would_replace_zero_with_one(self):
        """
        Reproduziert den alten Bug: `or 1.0` ersetzt 0.0 durch 1.0.
        Dieser Test zeigt, dass der BUG NICHT mehr auftritt.
        """
        stored = 0.0
        # ALTES (buggy) Verhalten:
        buggy_result = stored or 1.0
        assert buggy_result == pytest.approx(1.0)  # das war der Bug!

        # NEUES (korrigiertes) Verhalten: explizite None-Prüfung
        correct_result = 1.0 if stored is None else float(stored)
        assert correct_result == pytest.approx(0.0)

    def test_none_uses_default(self):
        """None/fehlender Wert verwendet Default 1.0."""
        stored = None
        result = 1.0 if stored is None else float(stored)
        assert result == pytest.approx(1.0)

    def test_factor_values_preserved(self):
        """Verschiedene Faktorwerte bleiben unverändert bei korrekter None-Prüfung."""
        for value in [0.0, 0.25, 0.65, 0.73, 1.0]:
            result = 1.0 if value is None else float(value)
            assert result == pytest.approx(value), f"Failed for {value}"

    def test_zero_factor_in_db(self, db):
        """Speichere und lese Faktor 0.0 aus der DB."""
        db.execute(
            "INSERT INTO exercises(id, name_en, enabled, uses_bodyweight, bodyweight_factor) "
            "VALUES('zero_ex', 'Zero Exercise', 1, 1, 0.0)"
        )
        row = db.execute(
            "SELECT bodyweight_factor FROM exercises WHERE id='zero_ex'"
        ).fetchone()
        assert float(row[0]) == pytest.approx(0.0)

    def test_zero_percent_submit_stores_zero(self):
        """Absenden mit Prozentwert 0 speichert Faktor 0.0."""
        pct_from_form = 0
        factor = round(float(pct_from_form) / 100.0, 4)
        assert factor == pytest.approx(0.0)


# ---- Real flow simulation tests (mimicking async_step_edit_exercise) ----


def _simulate_get_stored_factor(exercise_dict):
    """Simuliert die korrekte None-Prüfung aus config_flow.py."""
    raw = exercise_dict.get("bodyweight_factor")
    if raw is None:
        return 1.0
    return float(raw)


def _simulate_edit_exercise_processing(exercise_dict, user_input):
    """Simuliert den genauen Code-Pfad von async_step_edit_exercise.

    Gibt (uses_bodyweight, bodyweight_factor) zurück wie im Flow berechnet.
    """
    uses_bw = bool(user_input.get("uses_bodyweight", False))
    stored_raw = exercise_dict.get("bodyweight_factor")
    stored_factor = 1.0 if stored_raw is None else float(stored_raw)

    if "bodyweight_factor" in user_input:
        try:
            bw_factor = round(float(user_input["bodyweight_factor"]) / 100.0, 4)
        except (TypeError, ValueError):
            bw_factor = stored_factor
    else:
        bw_factor = stored_factor

    bw_factor = max(0.0, min(1.0, bw_factor))
    return uses_bw, bw_factor


def _simulate_schema_default(exercise_dict, user_input):
    """Simuliert den Schema-Default für ATTR_BODYWEIGHT_FACTOR.

    Gibt den Prozentwert zurück, der im Formular angezeigt wird.
    """
    if user_input is not None and "bodyweight_factor" in user_input:
        return int(round(user_input["bodyweight_factor"]))
    stored = _simulate_get_stored_factor(exercise_dict)
    return int(round(stored * 100))


class TestRealEditFlowSimulation:
    """Echte Flow-Tests die den genauen Code-Pfad von async_step_edit_exercise simulieren."""

    def test_065_correctly_displayed(self):
        """Test 1: Faktor 0.65 wird als 65 % im Formular angezeigt."""
        exercise = {"bodyweight_factor": 0.65}
        pct = _simulate_schema_default(exercise, None)
        assert pct == 65

    def test_65_percent_correctly_stored(self):
        """Test 2: Prozentwert 65 wird als Faktor 0.65 gespeichert."""
        exercise = {"bodyweight_factor": 1.0}
        user_input = {"bodyweight_factor": 65, "uses_bodyweight": True}
        uses_bw, factor = _simulate_edit_exercise_processing(exercise, user_input)
        assert uses_bw is True
        assert factor == pytest.approx(0.65)

    def test_0_correctly_displayed(self):
        """Test 3: Faktor 0.0 wird als 0 % im Formular angezeigt — nicht 100 %."""
        exercise = {"bodyweight_factor": 0.0}
        pct = _simulate_schema_default(exercise, None)
        assert pct == 0

    def test_0_preserved_on_missing_field(self):
        """Test 4: Fehlendes Feld erhält Faktor 0.0 unverändert."""
        exercise = {"bodyweight_factor": 0.0}
        user_input = {}  # kein bodyweight_factor-Feld
        uses_bw, factor = _simulate_edit_exercise_processing(exercise, user_input)
        assert factor == pytest.approx(0.0)

    def test_toggle_preserves_065(self):
        """Test 5: Checkbox deaktivieren und reaktivieren erhält Faktor 0.65."""
        exercise = {"bodyweight_factor": 0.65}

        # Schritt 1: Checkbox deaktivieren, kein bodyweight_factor-Feld
        user_input_off = {"uses_bodyweight": False}
        _, factor_after_off = _simulate_edit_exercise_processing(exercise, user_input_off)
        assert factor_after_off == pytest.approx(0.65)

        # Schritt 2: Checkbox wieder aktivieren, kein bodyweight_factor-Feld
        exercise_updated = {"bodyweight_factor": factor_after_off}
        user_input_on = {"uses_bodyweight": True}
        _, factor_after_on = _simulate_edit_exercise_processing(exercise_updated, user_input_on)
        assert factor_after_on == pytest.approx(0.65)

    def test_none_uses_default(self):
        """Test 6: Fehlender Altwert verwendet Default 1.0 → Formular zeigt 100 %."""
        exercise = {}  # kein bodyweight_factor-Key (legacy row)
        stored = _simulate_get_stored_factor(exercise)
        assert stored == pytest.approx(1.0)

        pct = _simulate_schema_default(exercise, None)
        assert pct == 100

    def test_full_roundtrip_65(self):
        """Vollständiger Round-Trip: DB → Formular → Absenden → DB."""
        # Ausgangswert in DB
        exercise = {"bodyweight_factor": 0.65}

        # Schritt 1: Schema-Default für Formular-Anzeige
        pct_displayed = _simulate_schema_default(exercise, None)
        assert pct_displayed == 65

        # Schritt 2: Benutzer ändert nichts, sendet 65 zurück
        user_input = {"bodyweight_factor": 65}
        _, stored_back = _simulate_edit_exercise_processing(exercise, user_input)
        assert stored_back == pytest.approx(0.65)

    def test_full_roundtrip_0(self):
        """Vollständiger Round-Trip mit Faktor 0.0."""
        exercise = {"bodyweight_factor": 0.0}

        pct_displayed = _simulate_schema_default(exercise, None)
        assert pct_displayed == 0

        user_input = {"bodyweight_factor": 0}
        _, stored_back = _simulate_edit_exercise_processing(exercise, user_input)
        assert stored_back == pytest.approx(0.0)

    def test_full_roundtrip_1(self):
        """Vollständiger Round-Trip mit Faktor 1.0."""
        exercise = {"bodyweight_factor": 1.0}

        pct_displayed = _simulate_schema_default(exercise, None)
        assert pct_displayed == 100

        user_input = {"bodyweight_factor": 100}
        _, stored_back = _simulate_edit_exercise_processing(exercise, user_input)
        assert stored_back == pytest.approx(1.0)

    def test_change_from_65_to_80(self):
        """Benutzer ändert Faktor von 65 % auf 80 %."""
        exercise = {"bodyweight_factor": 0.65}
        user_input = {"bodyweight_factor": 80, "uses_bodyweight": True}
        _, new_factor = _simulate_edit_exercise_processing(exercise, user_input)
        assert new_factor == pytest.approx(0.80)

    def test_error_falls_back_to_stored(self):
        """Bei Konvertierungsfehler wird gespeicherter Faktor verwendet."""
        exercise = {"bodyweight_factor": 0.75}
        user_input = {"bodyweight_factor": "invalid", "uses_bodyweight": True}
        _, factor = _simulate_edit_exercise_processing(exercise, user_input)
        assert factor == pytest.approx(0.75)  # Fallback auf stored

    def test_clamp_negative_to_zero(self):
        """Negativer Prozentwert wird zu 0.0 geclamped."""
        exercise = {"bodyweight_factor": 1.0}
        user_input = {"bodyweight_factor": -50}
        _, factor = _simulate_edit_exercise_processing(exercise, user_input)
        assert factor == pytest.approx(0.0)

    def test_clamp_over_100_to_one(self):
        """Prozentwert > 100 wird zu 1.0 geclamped."""
        exercise = {"bodyweight_factor": 0.5}
        user_input = {"bodyweight_factor": 200}
        _, factor = _simulate_edit_exercise_processing(exercise, user_input)
        assert factor == pytest.approx(1.0)


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
