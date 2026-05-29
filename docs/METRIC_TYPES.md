# Metric Types (Phase 1)

HAGym Phase 1 extends `set_logs` to support multiple training entry metric types in one table.

## Supported Metric Types

- `strength` (default)
- `bodyweight`
- `duration`
- `distance`
- `cardio`
- `hold`
- `custom`

## Design

- No separate `activity_logs` table is introduced.
- `set_logs.metric_type` controls which fields are relevant.
- Existing strength flows stay backward compatible.

## Storage Model

Strength rows use existing fields:

- `weight`
- `reps`
- `volume = weight * reps`

Non-strength rows can use optional fields:

- `duration_seconds`
- `distance_m`
- `calories`
- `steps`
- `avg_heart_rate`, `max_heart_rate`
- `avg_power_watts`, `max_power_watts`, `avg_speed_mps`
- `load_score`
- `intensity`
- `source`
- `added_weight` (for bodyweight entries)

## Load Score (v1)

- `duration` / `hold`: `duration_seconds / 60`
- `distance`: `duration_seconds / 60` if duration exists, else `distance_m / 1000`
- `cardio`: `(duration_seconds / 60) * intensity_factor`
  - `low=0.8`, `moderate=1.0`, `hard=1.4`, `very_hard=1.8`

## Analytics Compatibility

- Existing volume-based strength analytics remain unchanged.
- Non-strength rows are stored with `volume = 0` and therefore do not inflate kg volume totals.
- PR calculations remain strength-focused.

## Exercise Device Statistics (Metric-Type-Aware)

Exercise devices now expose statistics based on `exercise.metric_type`.

- `strength`: personal/household kg volume + personal/household kg PR + personal/household set count + last set
- `bodyweight`: reps/best reps/load/entries + last entry
- `duration` / `hold`: duration/best duration/load/entries + last entry
- `distance`: distance/duration/best distance/best pace/load + last entry
- `cardio`: duration/distance/calories/steps/heart rate/load/best pace + last entry
- `custom`: conservative generic activity stats (entries/load/duration/distance + last entry)

Deprecated:

- Generic exercise sensors `Gesamtvolumen` and `PR` are no longer created.
- Existing stale entities from older versions can be removed manually from Home Assistant.

## Service

Use `ha_fitness.save_activity` for non-strength entries.

Use existing strength services for strength logging:

- `ha_fitness.save_current_set`
- `ha_fitness.save_set`
- `ha_fitness.add_set_to_workout`

## Shared Activity Input Entities (v1)

For live dashboard input, HAGym now provides shared activity entities on the main device:

- `number.ha_fitness_duration_minutes`
- `number.ha_fitness_distance_km`
- `number.ha_fitness_calories`
- `number.ha_fitness_steps`
- `number.ha_fitness_avg_heart_rate`
- `number.ha_fitness_max_heart_rate`
- `number.ha_fitness_added_weight`
- `select.ha_fitness_intensity`
- `button.ha_fitness_save_activity`

Notes:

- Strength stays on `button.ha_fitness_save_set`.
- Non-strength metric types use `button.ha_fitness_save_activity`.
- Activity values are reset after successful activity save and on workout start/finish.

## Examples

Jogging:

```yaml
service: ha_fitness.save_activity
data:
  exercise_id: running
  metric_type: cardio
  duration_seconds: 1800
  distance_m: 5000
  avg_heart_rate: 145
  max_heart_rate: 172
  calories: 380
  intensity: moderate
  notes: "Locker gelaufen"
```

Plank:

```yaml
service: ha_fitness.save_activity
data:
  exercise_id: plank
  metric_type: hold
  duration_seconds: 90
  notes: "Sauber gehalten"
```

Stretching:

```yaml
service: ha_fitness.save_activity
data:
  exercise_id: stretching
  metric_type: duration
  duration_seconds: 600
```
