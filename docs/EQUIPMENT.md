# Equipment Catalog (Phase 2.4)

HAGym now supports an equipment catalog that links:

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

- `bench_station` — Bankdrückstation / Bench Station (mdi:bench)
- `cable_tower` — Kabelzugturm / Cable Tower (mdi:pulley)
- `squat_rack` — Kniebeugenständer / Squat Rack (mdi:weight-lifter)
- `dumbbell_area` — Kurzhantelbereich / Dumbbell Area (mdi:dumbbell)
- `rowing_station` — Ruderstation / Row Station (mdi:rowing)

Default exercises are backfilled to these devices where known.

## Naming model

Equipment now follows the same multilingual naming pattern as exercises and muscle groups:

- `name_en`
- `name_de`
- legacy `name` (kept for backward compatibility)

Display fallback order is:

1. `name_de`
2. `name_en`
3. `name`
4. `id`

So in German setups, default stations render with German labels.

## Options UI

In **Settings -> Devices & Services -> HAGym -> Configure**:

- Manage Equipment
- Add Equipment
- Edit Equipment
- Disable / Enable Equipment
- Assign Exercises

### Add equipment fields

- `equipment_id` (lowercase/underscore safe id)
- `name_de` (required in UI)
- `name_en` (optional)
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

## Device assignment cleanup (Phase 2.7)

Main integration device (`HAGym`) is reserved for global entities, for example:

- central workout controls (`active_equipment`, `active_exercise`, `weight`, `reps`, `notes`)
- workout action buttons (`start_workout`, `save_set`, `finish_workout`)
- global/personal/household overview sensors
- aggregate catalog/debug sensors like `equipment_catalog` and `equipment_statistics`

Equipment devices contain only equipment-scoped entities (for example one station's totals and `select_equipment` button).
Per-equipment sensors should not be duplicated on the main integration device.

If older duplicate entities still exist after update, they can stay in Home Assistant as unavailable stale entries.
You can remove them safely from the Home Assistant UI (**Settings -> Devices & Services -> Entities**).
Do **not** edit `/config/.storage/entity_registry` manually.

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
