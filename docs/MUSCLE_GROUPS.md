# Muscle Groups

HAGym supports muscle groups as a first-class catalog dimension in addition to equipment and exercises.

## Model

Relationship:

- Equipment -> Exercise -> Muscle Groups

Key rule:

- Muscle groups are assigned to exercises, not directly to equipment.

Set logs remain stored with:

- `user_id`
- `equipment_id`
- `exercise_id`
- `weight`, `reps`, `volume`

Muscle-group statistics are derived from those logs using exercise mappings.

Weekly muscle-group analytics follow the same derivation and compute weighted volume per mapping:

- `weighted_volume = set_logs.volume * exercise_muscle_groups.weight_factor`

## Tables

### `muscle_groups`

- `id` (TEXT, primary key)
- `name_en` (TEXT, required)
- `name_de` (TEXT, optional)
- `description` (TEXT, optional)
- `icon` (TEXT, optional)
- `body_region` (TEXT, optional)
- `enabled` (INTEGER, default `1`)
- `sort_order` (INTEGER, default `100`)
- `created_at` (TEXT, required)
- `updated_at` (TEXT, required)

### `exercise_muscle_groups`

- `exercise_id` (TEXT, required)
- `muscle_group_id` (TEXT, required)
- `role` (TEXT, default `primary`)
- `weight_factor` (REAL, default `1.0`)
- `created_at` (TEXT, required)
- `updated_at` (TEXT, required)
- Primary key: (`exercise_id`, `muscle_group_id`)

Roles:

- `primary` (default factor `1.0`)
- `secondary` (default factor `0.5`)
- `stabilizer` (default factor `0.25`)

## Statistics Derivation

Muscle-group metrics are computed by joining:

- `set_logs`
- `exercise_muscle_groups` on `exercise_id`
- `muscle_groups` on `muscle_group_id`

Derived metrics include:

- weighted volume: `SUM(set_logs.volume * weight_factor)`
- total sets
- last used timestamp
- top exercise by weighted volume

Scopes:

- global
- personal (resolved Home Assistant user)
- household (configured household user IDs)

## Notes

- Weight factors are approximation values for training-load attribution.
- They are not medical or biomechanical exact values.
- Equipment, exercises, and muscle groups are global catalogs.
- Logs and personal statistics remain user-specific.
- Personal analytics resolve to the active/selected Home Assistant user context.
