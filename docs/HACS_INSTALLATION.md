# HACS Installation Guide

## Prerequisites

- [HACS](https://hacs.xyz/) installed in your Home Assistant instance.
- Home Assistant 2024.1.0 or newer.

## Install via HACS Custom Repository

1. Open HACS in your Home Assistant sidebar.
2. Go to **Integrations**.
3. Click the three-dot menu (⋮) in the top-right corner and select **Custom repositories**.
4. Enter the repository URL:
   ```
   https://github.com/RTHeinemann/HAGym
   ```
   and select **Integration** as the category.
5. Click **Add**.
6. Find **HAGym** in the HACS integration list and click **Download**.
7. Restart Home Assistant.

## Add the Integration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **HAGym**.
3. Enter a display name (default: `HAGym`) and click **Submit**.

## What Gets Created

After setup, Home Assistant will create:

| Entity | Description |
|--------|-------------|
| `sensor.ha_fitness_status` | Current workout state (`ready` / `active`) |
| `sensor.ha_fitness_active_exercise` | Currently selected exercise or `none` |
| `sensor.ha_fitness_current_set_number` | Number of sets saved in the active workout |
| `sensor.ha_fitness_last_set` | Summary of the last saved set |
| `sensor.ha_fitness_current_set_volume` | Weight × reps for current set inputs |
| `sensor.ha_fitness_active_workout_summary` | Full workout state with attributes |
| `sensor.ha_fitness_total_volume` | Persisted total training volume (kg) |
| `sensor.ha_fitness_total_sets` | Persisted total set count |
| `sensor.ha_fitness_total_workouts` | Persisted total workout count |
| `sensor.ha_fitness_recent_sets` | Recent set list in attributes |
| `sensor.ha_fitness_exercise_catalog` | Enabled exercise count + full catalog attributes |
| `sensor.ha_fitness_exercise_statistics` | Exercises-with-sets count + grouped per-exercise stats |
| `button.ha_fitness_start_workout` | Starts a workout session |
| `button.ha_fitness_finish_workout` | Finishes a workout session |
| `button.ha_fitness_save_set` | Saves the current set using active inputs |
| `select.ha_fitness_active_exercise` | Dropdown to choose the active exercise |
| `number.ha_fitness_weight` | Weight input (0–500 kg, step 0.5) |
| `number.ha_fitness_reps` | Reps input (0–999, step 1) |
| `text.ha_fitness_notes` | Optional notes for the current set (max 255 chars) |

## Native Workout Flow

The integration supports a minimal native workout flow:

1. **Start Workout** – Press `button.ha_fitness_start_workout`
2. **Select Exercise** – Choose from `select.ha_fitness_active_exercise`
3. **Enter Weight** – Set `number.ha_fitness_weight`
4. **Enter Reps** – Set `number.ha_fitness_reps`
5. **Optional Notes** – Fill `text.ha_fitness_notes`
6. **Press Save Set** – Press `button.ha_fitness_save_set`
7. **See Results** – Check `sensor.ha_fitness_last_set` and `sensor.ha_fitness_active_workout_summary`
8. **Finish Workout** – Press `button.ha_fitness_finish_workout`

## SQLite Storage

- HACS installs only integration code.
- Runtime data is stored in:
  - `/config/ha_fitness/ha_fitness.db`
- The integration creates the folder/file automatically on startup.
- Data survives Home Assistant restarts, HACS updates, and integration re-installs.

## Available Services

Call these from **Developer Tools → Services**:

| Service | Description |
|---------|-------------|
| `ha_fitness.start_workout` | Transitions status to `active` |
| `ha_fitness.finish_workout` | Transitions status to `ready` |
| `ha_fitness.save_set` | Logs a set (exercise, weight, reps, optional notes); if inactive, creates and auto-finishes an implicit workout |
| `ha_fitness.refresh_statistics` | Reloads cached totals/PR/recent sets from SQLite |
| `ha_fitness.export_data` | Writes export JSON to `/config/ha_fitness/export.json` |

## Configure Exercises in UI (Options Flow)

You can manage exercises without manually calling services:

1. Go to **Settings → Devices & Services → HAGym → Configure / Options**
2. Use:
   - **Manage exercises**
   - **Add exercise**
   - **Edit exercise**
   - **Disable / enable exercise**

Exercise ID rules:

- Required and normalized to lowercase
- Allowed characters: letters, numbers, `_`, `-`
- In options UI, `-` is converted to `_`

Disabling exercises does **not** delete historical set logs.
Disabled exercises are removed from `select.ha_fitness_active_exercise`, but remain in catalog/statistics and can be re-enabled.

### Example: save_set

```yaml
service: ha_fitness.save_set
data:
  exercise: "Bench Press"
  weight: 80
  reps: 10
  notes: "Felt strong today"
```

> **Note:** `exercise` must not be empty, `weight` must be > 0, and `reps` must be > 0.
> The service will raise an error if validation fails.

## Dashboard

A ready-made native dashboard is available at
[`dashboards/ha_fitness_native_dashboard.yaml`](../dashboards/ha_fitness_native_dashboard.yaml).

## Current Limitations

- Native history views are currently limited to aggregate sensors plus `sensor.ha_fitness_recent_sets`.
- Fixed per-exercise PR/volume entities are still generated only for default built-in exercise IDs.
- Rich rendering of `sensor.ha_fitness_exercise_statistics` attributes may require custom dashboard cards.
- Advanced charts/cards are still provided mainly by YAML examples.

See [MIGRATION_FROM_YAML_TO_INTEGRATION.md](MIGRATION_FROM_YAML_TO_INTEGRATION.md) for the migration roadmap.

## Multi-User Attribution Notes (Phase 2.1)

- User attribution is based on Home Assistant service context (`call.context.user_id`).
- For best attribution accuracy, prefer Lovelace buttons that call services instead of direct button entities:
  - `ha_fitness.start_workout`
  - `ha_fitness.save_current_set`
  - `ha_fitness.finish_workout`
- Existing global sensors remain and aggregate all users.
- New personal and household sensors are available for multi-user dashboards.
