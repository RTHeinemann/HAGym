# Development Setup

## Requirements

- Home Assistant instance with package support enabled
- Lovelace dashboard editing/import access

## Steps

1. Copy `/packages/*.yaml` into your HA packages path.
2. Include packages from `configuration.yaml`.
3. Import/adapt `/dashboards/fitness_dashboard.yaml`.
4. Optionally copy `/dashboards/apexcharts_examples.yaml` cards.
5. Customize `/examples/exercise_metadata.yaml` for your gym.

## Validation

- Run Home Assistant config check.
- Verify helpers/entities are created.
- Start workout and save a sample set.
- Confirm PR/volume sensors update.
