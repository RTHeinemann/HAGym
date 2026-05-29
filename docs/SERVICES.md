# Services

This document highlights workout-management services added in v1.

## Live Workout Actions

- `ha_fitness.start_workout`
  - optional: `force` (default `false`)
  - behavior:
    - first call sets confirmation state (`start_confirm`)
    - second call within 10 seconds starts workout
    - `force: true` starts immediately
- `ha_fitness.finish_workout`
  - optional: `force` (default `false`)
  - behavior:
    - first call sets confirmation state (`finish_confirm`)
    - second call within 10 seconds finishes workout
    - `force: true` finishes immediately

## Equipment Selection

- `ha_fitness.select_equipment`
  - optional: `equipment_id`
  - expects stable equipment IDs (for example `cable_tower`)
  - labels shown in UI are localized via equipment `name_de` / `name_en`
  - legacy `name` is still supported internally for backward compatibility paths

## Workout CRUD

- `ha_fitness.create_workout`
  - required: `started_at`
  - optional: `user_id`, `ended_at`, `notes`, `status`
- `ha_fitness.update_workout`
  - required: `workout_id`
  - optional: `started_at`, `ended_at`, `notes`, `status`
- `ha_fitness.delete_workout`
  - required: `workout_id`
  - optional: `delete_sets` (default `true`)

## Set CRUD

- `ha_fitness.add_set_to_workout`
  - required: `workout_id`, `exercise_id`, `weight`, `reps`
  - optional: `user_id`, `equipment_id`, `notes`, `created_at`
- `ha_fitness.update_set`
  - required: `set_id`
  - optional: `equipment_id`, `exercise_id`, `weight`, `reps`, `notes`, `created_at`
- `ha_fitness.delete_set`
  - required: `set_id`

## Activity Logging (Phase 1)

- `ha_fitness.save_activity`
  - required: `exercise_id`
  - optional: `user_id`, `workout_id`, `equipment_id`, `metric_type`
  - optional activity fields:
    - `reps` (for bodyweight entries)
    - `duration_seconds`, `distance_m`, `calories`, `steps`
    - `avg_heart_rate`, `max_heart_rate`
    - `avg_power_watts`, `max_power_watts`, `avg_speed_mps`
    - `intensity`, `source`, `notes`, `created_at`, `added_weight`
  - behavior:
    - validates exercise existence and enabled state
    - resolves metric type from exercise when omitted
    - rejects `metric_type='strength'` and routes strength logging to set services
    - if `workout_id` is omitted and no active workout exists, creates an implicit completed workout

## Live Activity Button Flow

Besides the explicit `ha_fitness.save_activity` service call, the integration now supports a
shared live-input button flow:

- fill shared activity input entities (duration, distance, calories, heart-rate, intensity, ...)
- press `button.ha_fitness_save_activity`
- coordinator resolves active exercise metric type and validates required fields
- entry is saved through the same activity backend path

Validation examples:

- strength exercise selected -> blocked with "use save set"
- duration/hold/cardio -> require duration
- distance -> require distance
- bodyweight -> require reps >= 1
- custom -> require at least one activity field

## Validation

- `weight >= 0`
- `reps >= 1`
- `started_at <= ended_at` when both provided
- referenced workout/set/exercise/equipment must exist

All datetime fields use ISO timestamps.
