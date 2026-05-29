# HAGym

Home Assistant-native fitness and workout tracking inspired by the Energy Dashboard.

## Mission

Build a local-first, privacy-first fitness subsystem for Home Assistant with:

- workout tracking
- exercise history
- PR tracking
- weekly/monthly/yearly statistics
- NFC/QR gym workflows
- recovery analytics foundations
- dashboard-first UX

## Core Principles

- Home Assistant first
- Local-first and no cloud dependency
- YAML-compatible and modular
- Mobile-friendly, NFC/QR optimized
- Long-term maintainable
- Multi-user-ready architecture (even during MVP)

## Installation

### Option 1 – HACS Custom Integration (recommended going forward)

1. Add this repository as a custom HACS repository (category: **Integration**):
   ```
   https://github.com/RTHeinemann/HAGym
   ```
2. Download **HAGym** from HACS and restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **HAGym**.

> ✅ The HACS integration now includes SQLite-backed persistence (Phase 2).
> Data is stored locally at `/config/ha_fitness/ha_fitness.db` and survives restart/update.

See [`docs/HACS_INSTALLATION.md`](docs/HACS_INSTALLATION.md) for full details.

### Option 2 – YAML Prototype (legacy / feature-complete prototype)

1. Copy package files from `/packages` into your Home Assistant `packages` setup.
2. Include dashboard YAML from `/dashboards` in Lovelace.
3. Adapt exercise metadata in `/examples/exercise_metadata.yaml`.
4. Validate entity naming uses `fitness_*` prefix.

See [`docs/DEVELOPMENT_SETUP.md`](docs/DEVELOPMENT_SETUP.md) for a complete setup flow.

---

## Current Phase

This repository provides **Phase 2 (SQLite-backed native persistence)** with:

### HACS Native Integration

- `select.ha_fitness_active_exercise` – dropdown for 8 built-in exercises
- `select.ha_fitness_active_equipment` – equipment/station selector for exercise filtering
- integration options UI for exercise catalog management (add/edit/disable/re-enable)
- equipment catalog options UI (add/edit/disable/assign exercises)
- muscle group catalog options UI (add/edit/disable/assign to exercises)
- `number.ha_fitness_weight` and `number.ha_fitness_reps` – set input controls
- shared activity input entities on the main HAGym device:
  - `number.ha_fitness_duration_minutes`
  - `number.ha_fitness_distance_km`
  - `number.ha_fitness_calories`
  - `number.ha_fitness_steps`
  - `number.ha_fitness_avg_heart_rate`
  - `number.ha_fitness_max_heart_rate`
  - `number.ha_fitness_added_weight`
  - `select.ha_fitness_intensity`
- `text.ha_fitness_notes` – optional per-set notes
- `button.ha_fitness_save_set` – saves the current set with validation
- `button.ha_fitness_save_activity` – saves non-strength activity entries
- persisted workouts/sets in `/config/ha_fitness/ha_fitness.db`
- restored open workout/last set/statistics after Home Assistant restart
- aggregate sensors: total volume, total sets, total workouts
- generic catalog/statistics sensors for all exercises:
  - `sensor.ha_fitness_exercise_catalog`
  - `sensor.ha_fitness_exercise_statistics`
- generic equipment sensors:
  - `sensor.ha_fitness_equipment_catalog`
  - `sensor.ha_fitness_equipment_statistics`
- generic muscle group statistics sensor:
  - `sensor.ha_fitness_muscle_group_statistics`
- weekly aggregate analytics sensors (attribute-rich, low-entity approach):
  - `sensor.ha_fitness_personal_weekly_summary`
  - `sensor.ha_fitness_personal_weekly_exercise_statistics`
  - `sensor.ha_fitness_personal_weekly_muscle_group_statistics`
  - `sensor.ha_fitness_personal_weekly_volume_history` (last 12 weeks in attributes)
  - `sensor.ha_fitness_personal_training_balance`
  - `sensor.ha_fitness_household_weekly_summary`
- workout management aggregate sensor:
  - `sensor.ha_fitness_personal_recent_workouts`
- per-muscle-group Home Assistant devices and sensors (enabled groups only)
- per-exercise metric-type-aware sensors
  - strength: personal/household volume, PR, set count, last set
  - bodyweight: reps, best reps, training load, entry count
  - duration/hold: duration, best duration, load, entries
  - distance/cardio: distance, duration, pace, load (+ cardio fields such as calories/heart rate)
- recent sets sensor for dashboard history attributes
- improved `ha_fitness.save_set` service with implicit workout fallback
- workout management services:
  - `ha_fitness.create_workout`
  - `ha_fitness.update_workout`
  - `ha_fitness.delete_workout`
  - `ha_fitness.add_set_to_workout`
  - `ha_fitness.update_set`
  - `ha_fitness.delete_set`
  - `ha_fitness.save_activity` (non-strength activity logging)
- maintenance services: `ha_fitness.refresh_statistics`, `ha_fitness.export_data`
- Persistent notification on save errors
- Native dashboard at `dashboards/ha_fitness_native_dashboard.yaml`

### Device model (Phase 2.7)

- Main device (**HAGym**) contains global controls and overview sensors.
- Equipment-specific entities are assigned only to their equipment devices.
- Exercise-specific entities are assigned only to their exercise devices.
- Muscle-group-specific entities are assigned only to their muscle group devices.
- Relationship model: **Equipment -> Exercise -> Muscle Groups**
  - Equipment filters the available exercises.
  - Exercises define trained muscle groups via weighted mappings.
  - Set logs remain stored on `equipment_id` + `exercise_id`; muscle stats are derived from those logs.
- Integration entity count can still be high because Home Assistant counts entities across all devices.
- Older duplicate entities from previous versions can remain in the entity registry as unavailable entries.
  - Remove these in the Home Assistant UI if needed.
  - Do **not** edit `/config/.storage/entity_registry` manually.

### Exercise statistic migration note

- Generic exercise sensors `Gesamtvolumen` / `PR` are deprecated and no longer created for exercise devices.
- Replacement for dashboards:
  - `Gesamtvolumen` -> `Persönliches Gesamtvolumen` or `Haushalts-Gesamtvolumen`
  - `PR` -> `Persönlicher PR` or `Haushalts-PR`
- Old generic entities can remain as stale registry entries and can be removed manually in Home Assistant.

### Metric types (Phase 1)

`set_logs` now supports multiple metric types in one table:

- `strength` (existing weight/reps/volume flow)
- `bodyweight`
- `duration`
- `distance`
- `cardio`
- `hold`
- `custom`

Strength analytics remain volume (kg)-based. Non-strength activity rows store optional fields
like `duration_seconds`, `distance_m`, `calories`, `heart_rate`, and `load_score`, while
keeping `volume = 0` so existing strength volume analytics stay backward compatible.

Live input flow:
- strength exercises -> save with `Satz speichern`
- non-strength exercises -> save with `Aktivität speichern`
- activity inputs reset on real workout start, real workout finish, and after successful activity save

### YAML MVP+ Prototype (still more feature-complete for analytics)

- modular package examples
- dashboard and ApexCharts examples
- exercise + muscle-group metadata
- functional per-exercise set logging, PRs, and volume tracking
- recovery tracking and last-trained tracking
- expanded dashboard examples
- NFC/QR workflow docs and automation examples
- weekly/monthly/yearly muscle-group statistics
- SQLite backend docs and schema migration tracking

## Repository Structure

- `/packages` - Home Assistant package YAML modules (YAML prototype)
- `/dashboards` - Lovelace dashboards and chart examples
- `/custom_components/ha_fitness` - HACS-installable native integration
- `/docs` - architecture, roadmap, workflows, migration docs
- `/examples` - metadata models and config examples
- `/scripts` - helper scripts placeholder
- `/sqlite` - future backend notes
- `/assets` - static assets placeholder

## Multi-User Direction

MVP defaults can run single-user, but structure is future-ready:

```yaml
fitness:
  volume:
    user_id:
      exercise: total_volume
```

Planned model fields:

- `user_id`
- `display_name`
- `avatar`
- `color`
- `preferred_units`
- `active_training_plan`
- `created_at`

## Documentation Index

- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/NFC_WORKFLOW.md`](docs/NFC_WORKFLOW.md)
- [`docs/QR_WORKFLOW.md`](docs/QR_WORKFLOW.md)
- [`docs/WORKOUT_UX.md`](docs/WORKOUT_UX.md)
- [`docs/SQLITE_MIGRATION.md`](docs/SQLITE_MIGRATION.md)
- [`docs/STORAGE.md`](docs/STORAGE.md)
- [`docs/ANALYTICS.md`](docs/ANALYTICS.md)
- [`docs/WORKOUT_MANAGEMENT.md`](docs/WORKOUT_MANAGEMENT.md)
- [`docs/SERVICES.md`](docs/SERVICES.md)
- [`docs/EXERCISES.md`](docs/EXERCISES.md)
- [`docs/METRIC_TYPES.md`](docs/METRIC_TYPES.md)
- [`docs/EQUIPMENT.md`](docs/EQUIPMENT.md)
- [`docs/MUSCLE_GROUPS.md`](docs/MUSCLE_GROUPS.md)
- [`docs/HACS_PREPARATION.md`](docs/HACS_PREPARATION.md)
- [`docs/HACS_INSTALLATION.md`](docs/HACS_INSTALLATION.md)
- [`docs/MIGRATION_FROM_YAML_TO_INTEGRATION.md`](docs/MIGRATION_FROM_YAML_TO_INTEGRATION.md)
- [`docs/DEVELOPMENT_SETUP.md`](docs/DEVELOPMENT_SETUP.md)

## Contribution

Please read [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Phase 2.1 – Home Assistant User-Aware Multi-User Tracking

The integration now supports Home Assistant user-aware attribution via `call.context.user_id`.

- Sets and workouts are attributed to the calling HA user when actions use services.
- Existing pre-multi-user data is preserved and assigned to:
  - `legacy` (`Legacy / Pre-Multi-User Data`)
- Personal statistics are available per selected/current user.
- Household/family statistics aggregate configurable included users (or all enabled users by default).
- Existing global sensors are preserved for backward compatibility and aggregate all users.

Recommended dashboard action style for accurate attribution:
- `ha_fitness.start_workout`
- `ha_fitness.save_current_set`
- `ha_fitness.finish_workout`

Workout start/finish now use a backend two-step confirmation by default (10s timeout):
- first call asks for confirmation (`start_confirm` / `finish_confirm`)
- second call within timeout executes the action
- optional service field `force: true` bypasses confirmation (useful for automations)

> The integration does not parse or modify `/config/.storage/auth` and does not write to Home Assistant recorder tables.
