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

## Current Phase

This repository provides **Phase 1 (YAML MVP)** with:

- modular package examples
- dashboard and ApexCharts examples
- exercise + muscle-group metadata
- functional per-exercise set logging, PRs, and volume tracking
- NFC/QR workflow docs
- SQLite migration plan for future phases

## Repository Structure

- `/packages` - Home Assistant package YAML modules
- `/dashboards` - Lovelace dashboards and chart examples
- `/custom_components` - future native integration placeholder
- `/docs` - architecture, roadmap, workflows, migration docs
- `/examples` - metadata models and config examples
- `/scripts` - helper scripts placeholder
- `/sqlite` - future backend notes
- `/assets` - static assets placeholder

## Quick Start (Phase 1)

1. Copy package files from `/packages` into your Home Assistant `packages` setup.
2. Include dashboard YAML from `/dashboards` in Lovelace.
3. Adapt exercise metadata in `/examples/exercise_metadata.yaml`.
4. Validate entity naming uses `fitness_*` prefix.

See `/docs/DEVELOPMENT_SETUP.md` for a complete setup flow.

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
- [`docs/SQLITE_MIGRATION.md`](docs/SQLITE_MIGRATION.md)
- [`docs/HACS_PREPARATION.md`](docs/HACS_PREPARATION.md)
- [`docs/DEVELOPMENT_SETUP.md`](docs/DEVELOPMENT_SETUP.md)

## Contribution

Please read [`CONTRIBUTING.md`](CONTRIBUTING.md).
