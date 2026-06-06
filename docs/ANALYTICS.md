# Analytics Sensors

HAGym exposes analytics as a controlled hybrid model on the main device.

Goal:

- Keep entity count low and predictable.
- Avoid per-metric-per-exercise/equipment/muscle sensor explosion.
- Provide rich details through compact attribute payloads.

Note:

- This document covers core totals, daily metric buckets, and weekly history.
- Exercise device statistics are metric-type-aware and separate from weekly aggregate sensors.
- Strength keeps kg volume/PR semantics; non-strength exercise devices use duration/distance/load/cardio metrics.

## Core Total Sensors (Fixed Set)

Personal core totals:

- `sensor.ha_fitness_personal_core_total_strength_volume`
- `sensor.ha_fitness_personal_core_total_activity_load`
- `sensor.ha_fitness_personal_core_total_duration_minutes`
- `sensor.ha_fitness_personal_core_total_distance_km`
- `sensor.ha_fitness_personal_core_total_reps`
- `sensor.ha_fitness_personal_core_total_sets`

Household core totals:

- `sensor.ha_fitness_household_core_total_strength_volume`
- `sensor.ha_fitness_household_core_total_activity_load`
- `sensor.ha_fitness_household_core_total_duration_minutes`
- `sensor.ha_fitness_household_core_total_distance_km`
- `sensor.ha_fitness_household_core_total_reps`
- `sensor.ha_fitness_household_core_total_sets`

These use `state_class: total` (not `total_increasing`) because edited/deleted entries can reduce totals.

## Daily Metric Statistics Sensors

- `sensor.ha_fitness_personal_daily_metric_statistics`
- `sensor.ha_fitness_household_daily_metric_statistics`

Default payload:

- `day_count = 90`
- zero-filled days included
- capped nested breakdown lists (top exercises/equipment/muscle groups) to avoid oversized attributes

Entity-count control:

- No per-exercise metric daily sensors
- No per-equipment metric daily sensors
- No per-muscle-group metric daily sensors

## Weekly Sensor Set (Backward Compatible)

- `sensor.ha_fitness_personal_weekly_summary`
- `sensor.ha_fitness_personal_weekly_exercise_statistics`
- `sensor.ha_fitness_personal_weekly_muscle_group_statistics`
- `sensor.ha_fitness_personal_weekly_volume_history`
- `sensor.ha_fitness_personal_weekly_metric_history`
- `sensor.ha_fitness_personal_training_balance`
- `sensor.ha_fitness_household_weekly_summary`
- `sensor.ha_fitness_household_weekly_metric_history`

## Timeframe

Current week summary sensors:

- Week start: Monday 00:00 (Home Assistant local timezone)
- Week end: next Monday 00:00
- SQLite query boundaries are converted to UTC ISO timestamps

`sensor.ha_fitness_personal_weekly_volume_history`:

- Returns the last 12 weeks (including current week) in one attribute list.
- Uses weighted muscle-group volume and category buckets (push/pull/legs/core).
- Keeps entity count low by exposing history as attributes instead of extra entities.

`sensor.ha_fitness_personal_weekly_metric_history` and
`sensor.ha_fitness_household_weekly_metric_history`:

- Return the last 12 weeks (including current week) as attribute list `weeks`.
- Track metric-type-aware weekly history across `strength`, `bodyweight`, `duration`,
  `hold`, `distance`, `cardio`, and `custom`.
- Keep `strength_volume_kg` separate from activity `load_score`.
- Empty weeks are returned as zero-filled rows to keep charts stable.

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
  - entity: sensor.ha_fitness_personal_weekly_metric_history
  - entity: sensor.ha_fitness_household_weekly_summary
  - entity: sensor.ha_fitness_household_weekly_metric_history
  - entity: sensor.ha_fitness_personal_training_balance
```

## Weekly Metric History (ApexCharts, Optional)

### Weekly Activity Load (Stacked)

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Wochenlast nach Metrik
chart_type: bar
stacked: true
span:
  start: week
series:
  - entity: sensor.ha_fitness_personal_weekly_metric_history
    name: Bodyweight
    type: column
    data_generator: |
      return (entity.attributes.weeks || []).map((week) => [new Date(week.week_start).getTime(), week.bodyweight_load_score || 0]);
  - entity: sensor.ha_fitness_personal_weekly_metric_history
    name: Duration
    type: column
    data_generator: |
      return (entity.attributes.weeks || []).map((week) => [new Date(week.week_start).getTime(), week.duration_load_score || 0]);
  - entity: sensor.ha_fitness_personal_weekly_metric_history
    name: Hold
    type: column
    data_generator: |
      return (entity.attributes.weeks || []).map((week) => [new Date(week.week_start).getTime(), week.hold_load_score || 0]);
  - entity: sensor.ha_fitness_personal_weekly_metric_history
    name: Distance
    type: column
    data_generator: |
      return (entity.attributes.weeks || []).map((week) => [new Date(week.week_start).getTime(), week.distance_load_score || 0]);
  - entity: sensor.ha_fitness_personal_weekly_metric_history
    name: Cardio
    type: column
    data_generator: |
      return (entity.attributes.weeks || []).map((week) => [new Date(week.week_start).getTime(), week.cardio_load_score || 0]);
  - entity: sensor.ha_fitness_personal_weekly_metric_history
    name: Custom
    type: column
    data_generator: |
      return (entity.attributes.weeks || []).map((week) => [new Date(week.week_start).getTime(), week.custom_load_score || 0]);
```

### Weekly Cardio Overview

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Cardio Wochenübersicht
graph_span: 12w
series:
  - entity: sensor.ha_fitness_personal_weekly_metric_history
    name: Cardio Minuten
    data_generator: |
      return (entity.attributes.weeks || []).map((week) => [new Date(week.week_start).getTime(), week.cardio_minutes || 0]);
  - entity: sensor.ha_fitness_personal_weekly_metric_history
    name: Cardio km
    data_generator: |
      return (entity.attributes.weeks || []).map((week) => [new Date(week.week_start).getTime(), week.cardio_km || 0]);
  - entity: sensor.ha_fitness_personal_weekly_metric_history
    name: Kalorien
    data_generator: |
      return (entity.attributes.weeks || []).map((week) => [new Date(week.week_start).getTime(), week.cardio_calories || 0]);
```

### Weekly Distance (Distance + Cardio km)

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Distanz pro Woche
chart_type: bar
span:
  start: week
series:
  - entity: sensor.ha_fitness_personal_weekly_metric_history
    name: Distance km
    type: column
    data_generator: |
      return (entity.attributes.weeks || []).map((week) => [new Date(week.week_start).getTime(), (week.distance_km || 0) + (week.cardio_km || 0)]);
```

### Weekly Total Training (Strength + Activity)

```yaml
type: markdown
title: Weekly Total Training
content: >-
  {% set m = state_attr('sensor.ha_fitness_personal_weekly_metric_history', 'weeks') or [] %}
  {% set v = state_attr('sensor.ha_fitness_personal_weekly_volume_history', 'weeks') or [] %}
  {% set cw_m = m[-1] if m else {} %}
  {% set cw_v = v[-1] if v else {} %}
  Aktuelle Woche:  
  - Strength Volumen: **{{ (cw_m.get('total_strength_volume_kg', 0) | float(0)) | round(1) }} kg**  
  - Activity Load: **{{ (cw_m.get('total_activity_load_score', 0) | float(0)) | round(1) }} load**  
  - Minuten: **{{ (cw_m.get('total_minutes', 0) | float(0)) | round(1) }} min**  
  - Distanz: **{{ (cw_m.get('total_distance_km', 0) | float(0)) | round(2) }} km**  
  - Kalorien: **{{ (cw_m.get('total_calories', 0) | float(0)) | round(0) }} kcal**  
  - Push/Pull/Legs (kg): **{{ (cw_v.get('push_volume', 0) | float(0)) | round(1) }} / {{ (cw_v.get('pull_volume', 0) | float(0)) | round(1) }} / {{ (cw_v.get('legs_volume', 0) | float(0)) | round(1) }}**
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

## Custom Lovelace Cards (Energy-Inspired Pattern)

HAGym uses two separate cards:

- `custom:hagym-date-selection` (reusable period selector)
- `custom:hagym-period-dashboard-card` (analytics dashboard consuming selected period)

Resources:

```yaml
resources:
  - url: /hagym_static/hagym-date-selection-card.js?v=1.0.3.7
    type: module
  - url: /hagym_static/hagym-period-dashboard-card.js?v=1.0.3.7
    type: module
```

Embedded selector:

```yaml
type: custom:hagym-period-dashboard-card
daily_metric_entity: sensor.ha_fitness_personal_daily_metric_statistics
metric_history_entity: sensor.ha_fitness_personal_weekly_metric_history
volume_history_entity: sensor.ha_fitness_personal_weekly_volume_history
show_embedded_date_selection: true
collection_key: hagym
```

Separate selector + dashboard:

```yaml
views:
  - title: HAGym
    path: hagym
    type: sections
    footer:
      card:
        type: custom:hagym-date-selection
        collection_key: hagym
        placement: inline
        compact: true
        opening_direction: right
        vertical_opening_direction: up
    sections:
      - type: grid
        cards:
          - type: custom:hagym-period-dashboard-card
            daily_metric_entity: sensor.ha_fitness_personal_daily_metric_statistics
            metric_history_entity: sensor.ha_fitness_personal_weekly_metric_history
            volume_history_entity: sensor.ha_fitness_personal_weekly_volume_history
            show_embedded_date_selection: false
            collection_key: hagym
```

Notes:

- The selector is inspired by Home Assistant Energy UX, but is fully HAGym-owned and does not import Energy internals.
- Periods like `last_7_days` / `last_30_days` are approximated from weekly buckets in v1.
