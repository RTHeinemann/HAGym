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
- Equipment as Home Assistant devices with per-equipment statistics sensors
- Optional per-equipment action button: `button.<equipment>_select_equipment`

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

New equipment is stored globally and appears as a Home Assistant device with equipment sensors after integration reload (or immediately if Home Assistant reloads entities).

## Hybrid UX (global input + equipment devices)

Primary workout input remains global:

1. `select.ha_fitness_active_equipment`
2. `select.ha_fitness_active_exercise`
3. `number.ha_fitness_weight`
4. `number.ha_fitness_reps`
5. `text.ha_fitness_notes`
6. `button.ha_fitness_save_set`
7. `button.ha_fitness_start_workout` / `button.ha_fitness_finish_workout`

Equipment devices are primarily used for:

- identity and dashboards
- statistics sensors
- optional "select this equipment" action button
- future NFC/QR and area/device organization

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
