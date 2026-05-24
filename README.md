# HA Fitness Tracker

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
   https://github.com/RTHeinemann/HAFitness
   ```
2. Download **HA Fitness Tracker** from HACS and restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **HA Fitness Tracker**.

> ⚠️ The HACS integration now supports a minimal native workout flow (Phase 1.7).
> The YAML packages below remain a more feature-complete prototype for analytics and history
> until SQLite persistence and PR tracking are implemented natively.

See [`docs/HACS_INSTALLATION.md`](docs/HACS_INSTALLATION.md) for full details.

### Option 2 – YAML Prototype (legacy / feature-complete prototype)

1. Copy package files from `/packages` into your Home Assistant `packages` setup.
2. Include dashboard YAML from `/dashboards` in Lovelace.
3. Adapt exercise metadata in `/examples/exercise_metadata.yaml`.
4. Validate entity naming uses `fitness_*` prefix.

See [`docs/DEVELOPMENT_SETUP.md`](docs/DEVELOPMENT_SETUP.md) for a complete setup flow.

---

## Current Phase

This repository provides **Phase 1.7 (Native Entity Migration Start)** with:

### HACS Native Integration

- `select.ha_fitness_active_exercise` – dropdown for 8 built-in exercises
- `number.ha_fitness_weight` and `number.ha_fitness_reps` – set input controls
- `text.ha_fitness_notes` – optional per-set notes
- `button.ha_fitness_save_set` – saves the current set with validation
- 5 sensors: status, active exercise, set number, last set, volume, summary
- Improved `ha_fitness.save_set` service with strict validation
- Persistent notification on save errors
- Native dashboard at `dashboards/ha_fitness_native_dashboard.yaml`

### YAML MVP+ Prototype (still more feature-complete for analytics)

- modular package examples
- dashboard and ApexCharts examples
- exercise + muscle-group metadata
- functional per-exercise set logging, PRs, and volume tracking
- recovery tracking and last-trained tracking
- expanded dashboard examples
- NFC/QR workflow docs and automation examples
- weekly/monthly/yearly muscle-group statistics
- SQLite migration plan for **Phase 2**

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
- [`docs/HACS_PREPARATION.md`](docs/HACS_PREPARATION.md)
- [`docs/HACS_INSTALLATION.md`](docs/HACS_INSTALLATION.md)
- [`docs/MIGRATION_FROM_YAML_TO_INTEGRATION.md`](docs/MIGRATION_FROM_YAML_TO_INTEGRATION.md)
- [`docs/DEVELOPMENT_SETUP.md`](docs/DEVELOPMENT_SETUP.md)

## Contribution

Please read [`CONTRIBUTING.md`](CONTRIBUTING.md).
