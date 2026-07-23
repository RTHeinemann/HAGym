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

- `primary` (default share 60% of total weight)
- `secondary` (default share 30% of total weight)
- `stabilizer` (default share 10% of total weight)

### Normalized Weighting

Since v2, the sum of all `weight_factor` values for a single exercise must equal **exactly 1.0** (tolerance ±0.001). This ensures that muscle-group statistics represent the full training volume without artificial multiplication.

**How it works:**

- When assigning muscle groups via the options flow, after selecting primary/secondary/stabilizer groups, a new step `assign_muscle_groups_set_weights` appears with percentage fields (0–100%) for each selected group.
- The UI shows percentages; internally values are stored as decimals 0.0–1.0.
- Server-side validation ensures: at least one muscle group is assigned, no duplicates across roles, all values in range [0%, 100%], and the sum equals exactly 100% (±0.001).

**Default pre-filling:**

| Scenario | Behavior |
|---|---|
| New assignment, all three roles present | Primary: 60%, Secondary: 30%, Stabilizer: 10%. Evenly distributed within each role; last entry absorbs rounding remainder. |
| One or more roles empty | The share of empty roles is redistributed proportionally to active roles. |
| Editing existing assignment with non-zero weights | Existing factors are normalized proportionally (`old_factor / sum(old_factors)`). |

**Backward compatibility:**

- No silent global migration of existing data.
- Legacy entries retain their original `weight_factor` values until the exercise is edited via the options flow.
- The old role-bucket API (`async_replace_muscle_groups_for_exercise`) remains available for backward compatibility.

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

- Weight factors are normalized per exercise so their sum equals 1.0.
- They represent the proportion of training load attributed to each muscle group.
- Equipment, exercises, and muscle groups are global catalogs.
- Logs and personal statistics remain user-specific.
- Personal analytics resolve to the active/selected Home Assistant user context.
