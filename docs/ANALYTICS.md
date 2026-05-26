# Analytics Sensors

HAGym exposes weekly analytics as a small set of aggregate sensors on the main device.

Goal:

- Keep entity count low.
- Avoid per-week/per-exercise/per-muscle sensor explosion.
- Provide rich details through attributes.

## Weekly Sensor Set

- `sensor.ha_fitness_personal_weekly_summary`
- `sensor.ha_fitness_personal_weekly_exercise_statistics`
- `sensor.ha_fitness_personal_weekly_muscle_group_statistics`
- `sensor.ha_fitness_personal_training_balance`
- `sensor.ha_fitness_household_weekly_summary`

## Timeframe

Current week only (v1):

- Week start: Monday 00:00 (Home Assistant local timezone)
- Week end: next Monday 00:00
- SQLite query boundaries are converted to UTC ISO timestamps

Each sensor exposes:

- `week_start`
- `week_end`
- `timezone`

## Personal vs Household Scope

- Personal analytics use resolved Home Assistant `user_id`.
- Household analytics use configured included users.
- Legacy rows stay separate unless included by scope.

## Lovelace / Mushroom Examples

### Weekly Overview (Entities)

```yaml
type: entities
title: HAGym Weekly Analytics
entities:
  - entity: sensor.ha_fitness_personal_weekly_summary
  - entity: sensor.ha_fitness_household_weekly_summary
  - entity: sensor.ha_fitness_personal_training_balance
```

### Top Exercise and Top Muscle (Template)

```yaml
type: markdown
title: Weekly Focus
content: >-
  {% set s = state_attr('sensor.ha_fitness_personal_weekly_summary', 'top_exercise_name') %}
  {% set m = state_attr('sensor.ha_fitness_personal_weekly_summary', 'top_muscle_group_name') %}
  Top exercise: **{{ s or 'n/a' }}**  
  Top muscle group: **{{ m or 'n/a' }}**
```

### Exercise List from Attributes (Template)

```yaml
type: markdown
title: Personal Weekly Exercises
content: >-
  {% set rows = state_attr('sensor.ha_fitness_personal_weekly_exercise_statistics', 'exercises') or [] %}
  {% for row in rows %}
  - **{{ row.exercise_name or row.exercise_id }}**: {{ (row.volume | float(0)) | round(1) }} kg ({{ row.sets }} sets)
  {% endfor %}
```

### Muscle Group List from Attributes (Template)

```yaml
type: markdown
title: Personal Weekly Muscle Groups
content: >-
  {% set rows = state_attr('sensor.ha_fitness_personal_weekly_muscle_group_statistics', 'muscle_groups') or [] %}
  {% for row in rows %}
  - **{{ row.muscle_group_name or row.muscle_group_id }}**: {{ (row.volume | float(0)) | round(1) }} kg
  {% endfor %}
```

## Optional ApexCharts

ApexCharts is optional. If installed, weekly trend/history charts can be added later by reading these aggregate attributes or by adding dedicated trend endpoints in a future version.
