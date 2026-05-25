# Equipment Catalog (Phase 2.4)

HA Fitness now supports an equipment catalog that links:

`Equipment -> Exercises -> Sets -> Statistics`

## What is included

- Equipment catalog table (`equipment`)
- Exercise-to-equipment mapping (`exercises.equipment_id`)
- Set log equipment attribution (`set_logs.equipment_id`)
- Active equipment selector entity: `select.ha_fitness_active_equipment`
- Equipment catalog/statistics sensors:
  - `sensor.ha_fitness_equipment_catalog`
  - `sensor.ha_fitness_equipment_statistics`

## Default equipment

- `bench_station` — Bench Station (mdi:bench)
- `cable_tower` — Cable Tower (mdi:pulley)
- `squat_rack` — Squat Rack (mdi:weight-lifter)
- `dumbbell_area` — Dumbbell Area (mdi:dumbbell)
- `rowing_station` — Row Station (mdi:rowing)

Default exercises are backfilled to these devices where known.

## Options UI

In **Settings -> Devices & Services -> HA Fitness -> Configure**:

- Manage Equipment
- Add Equipment
- Edit Equipment
- Disable / Enable Equipment
- Assign Exercises

### Add equipment fields

- `equipment_id` (lowercase/underscore safe id)
- `name`
- `description`
- `icon`
- `location`
- `enabled`
- `sort_order`

## Exercise filtering

The workflow is:

1. Select active equipment (`select.ha_fitness_active_equipment`)
2. Exercise selector (`select.ha_fitness_active_exercise`) is filtered to mapped exercises
3. Save set

If no equipment is selected (`All Equipment`), all enabled exercises are shown.

## Set logging behavior

When a set is saved:

- Selected equipment is stored in `set_logs.equipment_id`
- If no equipment is selected, equipment is derived from the exercise mapping
- Unknown/custom exercises can keep `equipment_id = NULL`

## Statistics behavior

Equipment statistics include:

- total volume
- total sets
- total trainings
- top exercise
- last used timestamp
- personal volume
- household volume

## Future NFC/QR preparation

A service hook is available for automated switching:

- `ha_fitness.select_equipment`

This supports future NFC/QR automations that pre-select gym stations without requiring dashboard navigation changes.
