# SQLite Migration Plan

## Objective

Move from helper-centric MVP storage toward structured set logging without breaking dashboards.

## Target Schema (initial)

- `Workout(id, user_id, started_at, finished_at)`
- `Exercise(id, name, muscle_group, equipment)`
- `SetLog(id, workout_id, exercise_id, set_number, weight, reps, volume, notes, created_at)`

## Migration Strategy

1. Keep current helper entities as compatibility layer.
2. Begin writing new sets to SQLite in parallel.
3. Read analytics from SQL sensors first, then deprecate helper aggregates.
4. Preserve user-scoped keys from day one (`user_id` on Workout).
