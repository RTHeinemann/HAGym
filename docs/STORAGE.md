# HAGym Storage

## Database Path

HAGym stores training data in:

- `/config/ha_fitness/ha_fitness.db`

In integration code this is resolved with:

- `hass.config.path("ha_fitness", "ha_fitness.db")`

## Installation and Runtime Behavior

- HACS installs only integration code in `custom_components/ha_fitness/`.
- The SQLite directory/file is created automatically at runtime.
- The database is **not** stored inside `custom_components/`.

## Persistence Guarantees

- Data survives Home Assistant restarts.
- Data survives HACS integration updates.
- Data usually remains after integration removal/re-install unless manually deleted.

## Backup and Removal

- Include `/config/ha_fitness/ha_fitness.db` in regular Home Assistant backups.
- To fully remove training data, stop Home Assistant and manually delete:
  - `/config/ha_fitness/ha_fitness.db`

## Schema Versioning

- Schema migrations are tracked in `schema_migrations`.
- Current version is applied automatically during startup.

## Recorder and Cloud

- HAGym does **not** write directly to Home Assistant recorder DB tables.
- HAGym has no cloud storage dependency.

## Multi-User Schema (v2)

Schema migration v2 adds:

- `users` table (`id`, `display_name`, `enabled`, `created_at`)
- `workouts.user_id`
- `set_logs.user_id`

Backfill behavior:

- Legacy rows from schema v1 are assigned to user id `legacy`.
- Legacy user record is created as `Legacy / Pre-Multi-User Data`.

Indexes:

- `idx_workouts_user_id_started_at`
- `idx_set_logs_user_id_created_at`
- `idx_set_logs_user_id_exercise_created_at`

Aggregation behavior:

- `user_id=None` in personal/global queries means all users.
- `user_ids=None` in household queries means all enabled users from `users`.

## Exercise Catalog Schema (v3)

Schema migration v3 adds:

- `exercises` table for stable IDs + localized names (`name_en`, `name_de`)
- `set_logs.exercise_id` for stable internal exercise attribution

Backfill behavior:

- Existing `set_logs.exercise` labels are mapped to known default `exercise_id` values when possible.
- Legacy unknown/custom labels are preserved as-is with `exercise_id = NULL`.

Runtime behavior:

- `select.ha_fitness_active_exercise` now displays localized names from the catalog.
- The integration internally tracks stable `exercise_id`.
- Existing sensors remain available; per-exercise metrics are computed by ID with legacy fallback matching.
