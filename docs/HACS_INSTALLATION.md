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
   https://github.com/RTHeinemann/HAFitness
   ```
   and select **Integration** as the category.
5. Click **Add**.
6. Find **HA Fitness Tracker** in the HACS integration list and click **Download**.
7. Restart Home Assistant.

## Add the Integration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **HA Fitness Tracker**.
3. Enter a display name (default: `HA Fitness Tracker`) and click **Submit**.

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

## Available Services

Call these from **Developer Tools → Services**:

| Service | Description |
|---------|-------------|
| `ha_fitness.start_workout` | Transitions status to `active` |
| `ha_fitness.finish_workout` | Transitions status to `ready` |
| `ha_fitness.save_set` | Logs a set (exercise, weight, reps, optional notes) |

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

> ⚠️ Phase 1.7 implements the minimal native workout flow.
>
> - No persistence across HA restart yet — state resets on restart.
> - No per-exercise PR tracking yet.
> - No workout volume history yet.
> - No SQLite storage yet.
> - YAML packages in `/packages` remain more feature-complete for analytics.

See [MIGRATION_FROM_YAML_TO_INTEGRATION.md](MIGRATION_FROM_YAML_TO_INTEGRATION.md) for the migration roadmap.

