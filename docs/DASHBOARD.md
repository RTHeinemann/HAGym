# HAGym Dashboard Cards

HAGym now ships a modular, Energy-inspired dashboard approach:

- `custom:hagym-date-selection`
- `custom:hagym-period-dashboard-card`
- `custom:hagym-top-list-card`
- `custom:hagym-activity-load-card`
- `custom:hagym-balance-card`

The architecture stays intentionally small:

- one shared period selector
- multiple focused cards
- existing daily metric statistics as primary data source
- no new backend sensors
- no per-exercise/per-equipment/per-muscle entity explosion

## Static Resources

HAGym serves its Lovelace card files directly from the integration under:

- `/hagym_static/hagym-date-selection-card.js`
- `/hagym_static/hagym-period-dashboard-card.js`
- `/hagym_static/hagym-top-list-card.js`
- `/hagym_static/hagym-activity-load-card.js`
- `/hagym_static/hagym-balance-card.js`

Add them in Home Assistant:

`Settings -> Dashboards -> Resources -> Add Resource`

Type:

- `JavaScript Module`

Example:

```yaml
resources:
  - url: /hagym_static/hagym-date-selection-card.js
    type: module
  - url: /hagym_static/hagym-period-dashboard-card.js
    type: module
  - url: /hagym_static/hagym-top-list-card.js
    type: module
  - url: /hagym_static/hagym-activity-load-card.js
    type: module
  - url: /hagym_static/hagym-balance-card.js
    type: module
```

## Shared Period Selector

All cards react to the same shared selection state:

- localStorage key: `hagym-period-selection:<collection_key>`
- events:
  - `hagym-period-changed`
  - `hagym-date-selection-changed`

Use the same `collection_key` everywhere. The default is:

- `hagym`

The selector also supports:

- `placement: fixed-bottom`

That makes it usable like an Energy-style footer selector on desktop and mobile.

## Card Overview

### `custom:hagym-date-selection`

Reusable selector card with:

- previous / next navigation
- `Jetzt`
- period menu
- `fixed-bottom` placement option
- Energy-inspired fixed row + centered inner pill
- automatic desktop content-area detection for better centering
- optional manual desktop override

Example:

```yaml
type: custom:hagym-date-selection
collection_key: hagym
placement: fixed-bottom
opening_direction: right
vertical_opening_direction: up
desktop_sidebar_offset: auto
content_selector: null
debug_layout: false
full_width_row: true
max_width: 720
bottom_offset: 16
z_index: 10
```

Advanced selector options:

- `desktop_sidebar_offset`
  - `auto` (default)
  - `0`
  - a fixed number like `256`
- `max_width`
  - default `720`
- `bottom_offset`
  - default `16`
- `z_index`
  - default `10`
- `content_selector`
  - default `null`
  - if set, HAGym tries this selector first when measuring the Lovelace content area
- `debug_layout`
  - default `false`
  - logs detected layout source and rect via `console.debug`
- `full_width_row`
  - default `true`
  - keeps the fixed bottom row stretched across the detected content area

Desktop centering behavior:

- In `fixed-bottom` mode, HAGym now behaves more like the Energy selector:
  - an internal fixed row is positioned across the detected dashboard content area
  - the actual selector pill is centered inside that row
- On desktop, HAGym first tries `--ha-top-app-bar-width`.
- If that is not available, it prefers measuring the actual Lovelace content rect.
- If that is not available, it falls back to sidebar-offset logic.
- If Home Assistant layout detection is not enough in a custom setup, you can override it manually:

Optional content selector hint:

```yaml
type: custom:hagym-date-selection
collection_key: hagym
placement: fixed-bottom
desktop_sidebar_offset: auto
content_selector: hui-sections-view
```

```yaml
type: custom:hagym-date-selection
collection_key: hagym
placement: fixed-bottom
desktop_sidebar_offset: 256
```

Disable sidebar compensation completely:

```yaml
type: custom:hagym-date-selection
collection_key: hagym
placement: fixed-bottom
desktop_sidebar_offset: 0
```

### `custom:hagym-period-dashboard-card`

Existing overview card. It remains available for broader aggregate summaries and can still embed the selector or follow an external selector.

Example:

```yaml
type: custom:hagym-period-dashboard-card
title: HAGym Uebersicht
daily_metric_entity: sensor.ha_fitness_personal_daily_metric_statistics
metric_history_entity: sensor.ha_fitness_personal_weekly_metric_history
volume_history_entity: sensor.ha_fitness_personal_weekly_volume_history
collection_key: hagym
show_embedded_date_selection: false
```

### `custom:hagym-top-list-card`

Generic top-list card for:

- `muscle_groups`
- `exercises`
- `equipment`

Supported metrics:

- `strength_volume_kg`
- `activity_load_score`
- `duration_minutes`
- `distance_km`
- `reps`
- `entries`
- `sets`

Examples:

```yaml
type: custom:hagym-top-list-card
title: Trainingsvolumen pro Muskelgruppe
daily_metric_entity: sensor.ha_fitness_personal_daily_metric_statistics
collection_key: hagym
scope: muscle_groups
metric: strength_volume_kg
limit: 10
```

```yaml
type: custom:hagym-top-list-card
title: Trainingsvolumen pro Uebung
daily_metric_entity: sensor.ha_fitness_personal_daily_metric_statistics
collection_key: hagym
scope: exercises
metric: strength_volume_kg
limit: 10
```

```yaml
type: custom:hagym-top-list-card
title: Trainingsvolumen pro Equipment
daily_metric_entity: sensor.ha_fitness_personal_daily_metric_statistics
collection_key: hagym
scope: equipment
metric: strength_volume_kg
limit: 10
```

### `custom:hagym-activity-load-card`

Activity-load visualization using the daily buckets.

Supports:

- `group_by: day`
- `group_by: week`
- `group_by: month`

Example:

```yaml
type: custom:hagym-activity-load-card
title: Activity Load Ausdauer
daily_metric_entity: sensor.ha_fitness_personal_daily_metric_statistics
collection_key: hagym
group_by: day
```

### `custom:hagym-balance-card`

Balance card based on the daily `muscle_groups` breakdown.

Modes:

- `push_pull`
- `push_pull_legs`
- `upper_lower`

Example:

```yaml
type: custom:hagym-balance-card
title: Balance Push/Pull
daily_metric_entity: sensor.ha_fitness_personal_daily_metric_statistics
collection_key: hagym
mode: push_pull
```

## Official Dashboard Templates

Ready-made templates:

- `dashboards/hagym_energy_style_dashboard_raw.yaml`
  - for direct paste into the normal Home Assistant `Raw configuration editor`
  - starts directly with `views:`
  - does not use a top-level `title`
  - does not use `view.footer`
- `dashboards/hagym_energy_style_dashboard.yaml`
  - for YAML dashboard mode / repo-managed dashboard files
  - may keep a top-level `title`
- `dashboards/hagym_energy_style_dashboard_minimal.yaml`
  - compact raw-safe minimal variant

For the normal Raw configuration editor:

1. Create a new empty dashboard first.
2. Open `Dashboard -> Edit -> Raw configuration editor`.
3. Paste `dashboards/hagym_energy_style_dashboard_raw.yaml`.

Important:

- Pasting into the Raw configuration editor replaces the current dashboard configuration.
- Test in a new empty dashboard first before replacing an existing dashboard you already use every day.

## Template Notes

The templates use the stable integration entity ids:

- `sensor.ha_fitness_personal_daily_metric_statistics`
- `sensor.ha_fitness_personal_weekly_metric_history`
- `sensor.ha_fitness_personal_weekly_volume_history`

If your instance generated different ids because of renamed entities, adapt them in the YAML.

The raw template intentionally puts the selector into a normal section card:

```yaml
type: custom:hagym-date-selection
collection_key: hagym
placement: fixed-bottom
```

This is more reliable in the normal Raw configuration editor than relying on `view.footer`.

## Example: Separate Selector + Cards

```yaml
type: vertical-stack
cards:
  - type: custom:hagym-top-list-card
    title: Trainingsvolumen pro Muskelgruppe
    daily_metric_entity: sensor.ha_fitness_personal_daily_metric_statistics
    collection_key: hagym
    scope: muscle_groups
    metric: strength_volume_kg
  - type: custom:hagym-balance-card
    title: Balance Push/Pull
    daily_metric_entity: sensor.ha_fitness_personal_daily_metric_statistics
    collection_key: hagym
    mode: push_pull
  - type: custom:hagym-activity-load-card
    title: Activity Load Ausdauer
    daily_metric_entity: sensor.ha_fitness_personal_daily_metric_statistics
    collection_key: hagym
    group_by: day
  - type: custom:hagym-date-selection
    collection_key: hagym
    placement: fixed-bottom
    opening_direction: right
    vertical_opening_direction: up
```

## Troubleshooting

- If Home Assistant says `Custom element doesn't exist`, do a hard browser refresh and reload the companion app view.
- Open the resource URLs directly in the browser, for example:
  - `/hagym_static/hagym-top-list-card.js`
  - `/hagym_static/hagym-activity-load-card.js`
  - `/hagym_static/hagym-balance-card.js`
- If a card shows missing-entity warnings, check the referenced entity ids in Developer Tools -> States.
- Empty periods are expected to show friendly empty states instead of crashing.

## Compatibility

The new dashboard layer does not remove or replace:

- existing backend sensors
- `custom:hagym-period-dashboard-card`
- existing dashboard YAML files
- workout input controls

The minimal Energy-style dashboard works with native Home Assistant plus the HAGym cards only. No `apexcharts-card`, Mushroom, or `button-card` is required.
