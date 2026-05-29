# Analytics Sensors

HAGym exposes weekly analytics as a small set of aggregate sensors on the main device.

Goal:

- Keep entity count low.
- Avoid per-week/per-exercise/per-muscle sensor explosion.
- Provide rich details through attributes.

Note:

- This document focuses on weekly aggregate analytics.
- Exercise device statistics are metric-type-aware and separate from weekly aggregate sensors.
- Strength keeps kg volume/PR semantics; non-strength exercise devices use duration/distance/load/cardio metrics.

## Weekly Sensor Set

- `sensor.ha_fitness_personal_weekly_summary`
- `sensor.ha_fitness_personal_weekly_exercise_statistics`
- `sensor.ha_fitness_personal_weekly_muscle_group_statistics`
- `sensor.ha_fitness_personal_weekly_volume_history`
- `sensor.ha_fitness_personal_training_balance`
- `sensor.ha_fitness_household_weekly_summary`

## Timeframe

Current week summary sensors:

- Week start: Monday 00:00 (Home Assistant local timezone)
- Week end: next Monday 00:00
- SQLite query boundaries are converted to UTC ISO timestamps

`sensor.ha_fitness_personal_weekly_volume_history`:

- Returns the last 12 weeks (including current week) in one attribute list.
- Uses weighted muscle-group volume and category buckets (push/pull/legs/core).
- Keeps entity count low by exposing history as attributes instead of extra entities.

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
  - entity: sensor.ha_fitness_personal_weekly_volume_history
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

## ApexCharts (Optional)

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Trainingsvolumen pro Woche
  show_states: true
  colorize_states: true
chart_type: bar
stacked: true
span:
  start: week
series:
  - entity: sensor.ha_fitness_personal_weekly_volume_history
    name: Push
    type: column
    data_generator: |
      return entity.attributes.weeks.map((week) => {
        return [new Date(week.week_start).getTime(), week.push_volume];
      });
  - entity: sensor.ha_fitness_personal_weekly_volume_history
    name: Pull
    type: column
    data_generator: |
      return entity.attributes.weeks.map((week) => {
        return [new Date(week.week_start).getTime(), week.pull_volume];
      });
  - entity: sensor.ha_fitness_personal_weekly_volume_history
    name: Legs
    type: column
    data_generator: |
      return entity.attributes.weeks.map((week) => {
        return [new Date(week.week_start).getTime(), week.legs_volume];
      });
  - entity: sensor.ha_fitness_personal_weekly_volume_history
    name: Core
    type: column
    data_generator: |
      return entity.attributes.weeks.map((week) => {
        return [new Date(week.week_start).getTime(), week.core_volume];
      });
```

## Mushroom Summary (Optional)

```yaml
type: markdown
title: Wochenstatus
content: >-
  {% set hist = state_attr('sensor.ha_fitness_personal_weekly_volume_history', 'weeks') or [] %}
  {% set cur = hist[-1] if hist else {} %}
  {% set top_ex = cur.get('top_exercise_name') %}
  {% set top_mg = cur.get('top_muscle_group_name') %}
  Gesamt (kategorisiert): **{{ (cur.get('categorized_volume_total', 0) | float(0)) | round(1) }} kg**  
  Top Uebung: **{{ top_ex or 'n/a' }}**  
  Top Muskelgruppe: **{{ top_mg or 'n/a' }}**  
  Push/Pull/Legs: **{{ (cur.get('push_percent', 0) | float(0)) | round(0) }}% / {{ (cur.get('pull_percent', 0) | float(0)) | round(0) }}% / {{ (cur.get('legs_percent', 0) | float(0)) | round(0) }}%**
```

## Recent Workouts (Aggregate Sensor)

Workout management v1 adds one aggregate sensor:

- `sensor.ha_fitness_personal_recent_workouts`

It intentionally keeps entity count low and returns workout/set history in attributes.

### Example (Template Card)

```yaml
type: markdown
title: Letzte Trainings
content: >-
  {% set rows = state_attr('sensor.ha_fitness_personal_recent_workouts', 'workouts') or [] %}
  {% for w in rows[:5] %}
  - **#{{ w.workout_id }}** {{ w.started_at }} ({{ w.total_sets }} Sätze, {{ (w.total_volume | float(0)) | round(1) }} kg)
  {% endfor %}
```

### Example Service Buttons

```yaml
type: entities
title: Workout Aktionen
entities:
  - type: button
    name: Training erstellen
    tap_action:
      action: call-service
      service: ha_fitness.create_workout
      data:
        started_at: "2026-05-26T08:00:00+02:00"
        ended_at: "2026-05-26T09:00:00+02:00"
        status: "completed"
```
