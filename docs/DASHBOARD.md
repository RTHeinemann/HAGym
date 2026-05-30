# HAGym Dashboard Cards

HAGym provides two minimal custom Lovelace cards following an Energy-inspired architecture:

1. `custom:hagym-date-selection` (standalone reusable selector)
2. `custom:hagym-period-dashboard-card` (analytics dashboard)

The selector writes period state to localStorage and dispatches events. The dashboard card reads that shared state and re-renders.

## Resources

Use the resource path that matches your setup.

HACS-style path:

```yaml
resources:
  - url: /hacsfiles/ha_fitness/hagym-date-selection-card.js
    type: module
  - url: /hacsfiles/ha_fitness/hagym-period-dashboard-card.js
    type: module
```

Alternative local/community path:

```yaml
resources:
  - url: /local/community/ha_fitness/hagym-date-selection-card.js
    type: module
  - url: /local/community/ha_fitness/hagym-period-dashboard-card.js
    type: module
```

## Card Files

- `/config/custom_components/ha_fitness/www/hagym-date-selection-card.js`
- `/config/custom_components/ha_fitness/www/hagym-period-dashboard-card.js`

## Example: Embedded Selector

```yaml
type: custom:hagym-period-dashboard-card
daily_metric_entity: sensor.ha_fitness_personal_daily_metric_statistics
metric_history_entity: sensor.ha_fitness_personal_weekly_metric_history
volume_history_entity: sensor.ha_fitness_personal_weekly_volume_history
show_embedded_date_selection: true
collection_key: hagym
```

## Example: Separate Selector + Dashboard

```yaml
type: vertical-stack
cards:
  - type: custom:hagym-period-dashboard-card
    daily_metric_entity: sensor.ha_fitness_personal_daily_metric_statistics
    metric_history_entity: sensor.ha_fitness_personal_weekly_metric_history
    volume_history_entity: sensor.ha_fitness_personal_weekly_volume_history
    show_embedded_date_selection: false
    collection_key: hagym
  - type: custom:hagym-date-selection
    collection_key: hagym
    opening_direction: right
    vertical_opening_direction: up
```

## Selector Config

- `collection_key` (default: `hagym`)
- `opening_direction` (`left` or `right`, default `right`)
- `vertical_opening_direction` (`up` or `down`, default `up`)
- `default_period` (default `this_week`)

## Dashboard Config

- `daily_metric_entity` (optional, preferred for exact period aggregation)
- `metric_history_entity` (optional fallback when daily data is unavailable)
- `volume_history_entity` (optional)
- `collection_key` (default: `hagym`)
- `title` (default: `HAGym`)
- `show_embedded_date_selection` (default: `true`)

## Notes

- This pattern is inspired by Home Assistant Energy (`energy-date-selection`) UX.
- HAGym does not import private Energy frontend modules.
- If `daily_metric_entity` is available, period aggregation is exact for day/week/month/year ranges.
- If only weekly history is available, rolling periods are approximated from weekly buckets.
