# Exercise Catalog and Translations

HAGym uses a SQLite-backed exercise catalog with stable IDs.

## Why IDs

- IDs are stable keys (for example `bench_press`).
- Display names can be localized without breaking stored history.
- Statistics (PR/volume) are calculated by `exercise_id`.

## Catalog Schema

Table: `exercises`

- `id` (TEXT, primary key)
- `name_en` (TEXT, required)
- `name_de` (TEXT, optional)
- `muscle_group` (TEXT, optional)
- `equipment` (TEXT, optional)
- `equipment_id` (TEXT, optional, references equipment catalog id)
- `enabled` (INTEGER, default `1`)
- `sort_order` (INTEGER, default `0`)
- `created_at` (TEXT, required)

`set_logs` also contains nullable `exercise_id` for backward compatibility.

## Relationship Model

HAGym uses this hierarchy:

- Equipment -> Exercise -> Muscle Groups

Important constraints:

- Equipment does not directly map to muscle groups.
- Exercises can be mapped to one or more muscle groups with a role and weight factor.
- Logged sets stay linked to `equipment_id` and `exercise_id`.
- Muscle-group statistics are derived from set logs via exercise-to-muscle mappings.

## Default Exercise IDs

- `bench_press` – Bench Press / Bankdrücken (`chest`)
- `squat` – Squat / Kniebeuge (`legs`)
- `deadlift` – Deadlift / Kreuzheben (`posterior_chain`)
- `shoulder_press` – Shoulder Press / Schulterdrücken (`shoulders`)
- `row` – Row / Rudern (`back`)
- `lat_pulldown` – Lat Pulldown / Latzug (`back`)
- `bicep_curl` – Bicep Curl / Bizepscurls (`biceps`)
- `tricep_pushdown` – Tricep Pushdown / Trizepsdrücken (`triceps`)

## Localized Display Names

- Active exercise select options are loaded from `exercises`.
- German (`de`) uses `name_de` when available, otherwise falls back to `name_en`.
- Other locales currently use `name_en`.

## Add or Manage Custom Exercises (UI)

You can manage exercises directly in Home Assistant:

1. Open **Settings → Devices & Services**
2. Open **HAGym**
3. Click **Configure / Options**
4. Use:
   - **Manage exercises**
   - **Add exercise**
   - **Edit exercise**
   - **Disable / enable exercise**
   - **Assign exercises** (equipment mapping)
   - **Manage muscle groups** -> **Assign muscle groups to exercise**

The integration still exposes services:

- `ha_fitness.add_exercise`
- `ha_fitness.update_exercise`
- `ha_fitness.disable_exercise`
- `ha_fitness.refresh_exercises`

Recommendations:

- Use lowercase IDs (for example `incline_bench_press`).
- Allowed characters: `a-z`, `0-9`, `_`, `-`.
- In options UI, `-` is normalized to `_`.
- Keep IDs stable after creation.
- Use `sort_order` to control active-exercise select ordering (default: `100`).
- Use `enabled=false` instead of deleting rows to preserve references.

When disabling an exercise:

- Historical set data is kept in SQLite.
- The exercise is removed from `select.ha_fitness_active_exercise`.
- The exercise remains visible in options flow edit/toggle lists.
- The exercise remains included in historical/statistical aggregation.

## Generic Exercise Sensors

The integration exposes two generic sensors to make dynamic/custom exercises visible in dashboards:

- `sensor.ha_fitness_exercise_catalog`
  - state: count of enabled exercises
  - attributes: `exercises`, `enabled_exercises`, `disabled_exercises`
- `sensor.ha_fitness_exercise_statistics`
  - state: count of exercises with logged sets
  - attribute: `by_exercise` containing:
    - `exercise_id`
    - `display_name`
    - `total_volume_global`, `total_sets_global`, `pr_global`
    - `total_volume_personal`, `total_sets_personal`, `pr_personal`
    - `total_volume_household`, `total_sets_household`, `pr_household`

Custom exercises appear here as soon as sets are logged for them.
Existing fixed per-exercise PR/volume sensors still only exist for the default built-in exercise IDs.
Those fixed per-exercise sensors are grouped under one Home Assistant device per exercise
(`HAGym Exercise`) instead of the central `HAGym Tracker` device.

## Backward Compatibility

- Older rows with only `set_logs.exercise` are preserved.
- Migration attempts to backfill `set_logs.exercise_id` for known names.
- Unknown legacy/custom exercise labels remain valid historical records.
