# HAGym Dashboard Cards

HAGym now ships a modular, Energy-inspired dashboard approach:

- `custom:hagym-date-selection`
- `custom:hagym-period-dashboard-card`
- `custom:hagym-stacked-history-card`
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
- `/hagym_static/hagym-stacked-history-card.js`
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
  - url: /hagym_static/hagym-date-selection-card.js?v=1.0.3.7
    type: module
  - url: /hagym_static/hagym-period-dashboard-card.js?v=1.0.3.7
    type: module
  - url: /hagym_static/hagym-stacked-history-card.js?v=1.0.3.12
    type: module
  - url: /hagym_static/hagym-top-list-card.js?v=1.0.3.7
    type: module
  - url: /hagym_static/hagym-activity-load-card.js?v=1.0.3.7
    type: module
  - url: /hagym_static/hagym-balance-card.js?v=1.0.3.7
    type: module
```

After frontend changes, increment the `?v=` cache-buster and do a hard browser refresh so Home Assistant does not keep serving an older card bundle.

## Shared Period Selector

All cards react to the same shared selection state:

- localStorage key: `hagym-period-selection:<collection_key>`
- events:
  - `hagym-period-changed`
  - `hagym-date-selection-changed`

Use the same `collection_key` everywhere. The default is:

- `hagym`

The selector supports:

- `placement: inline` for the preferred footer-card setup
- `placement: fixed-bottom` as an optional HAGym-owned fallback layout

## Card Overview

### `custom:hagym-date-selection`

Reusable selector card with:

- HAGym-owned period selection menu
- compact one-row layout
- previous / next navigation
- three-dot shortcut menu
- `Jetzt` inside the shortcut menu
- shared period state via `localStorage`
- optional `fixed-bottom` placement

Recommended production config when your dashboard mode supports a real footer:

```yaml
footer:
  card:
    type: custom:hagym-date-selection
    collection_key: hagym
    placement: inline
    compact: true
    opening_direction: right
    vertical_opening_direction: up
```

Recommended inline config for the normal Raw configuration editor or a regular section card:

```yaml
type: custom:hagym-date-selection
collection_key: hagym
placement: inline
compact: true
opening_direction: right
vertical_opening_direction: up
```

Optional advanced fixed-footer config remains available if you want HAGym itself to float the selector:

```yaml
type: custom:hagym-date-selection
collection_key: hagym
placement: fixed-bottom
compact: true
full_width_row: true
desktop_sidebar_offset: auto
max_width: 900
bottom_offset: 16
z_index: 10
opening_direction: right
vertical_opening_direction: up
content_selector: null
debug_layout: false
```

Advanced selector options:

- `desktop_sidebar_offset`
  - `auto` (default)
  - `0`
  - a fixed number like `256`
- `max_width`
  - default `900`
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

Desktop centering behavior in `fixed-bottom` mode:

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

### `custom:hagym-stacked-history-card`

Energy-style stacked history chart built from the existing daily metric statistics.

Highlights:

- automatic day / week / month buckets based on the shared HAGym footer period
- stacked bars for top items across the visible range
- remaining items collapse into `Andere`
- hover tooltip on desktop
- tap-to-pin tooltip on mobile
- no new backend sensors

Example:

```yaml
type: custom:hagym-stacked-history-card
title: Trainingsvolumen pro Muskelgruppe
daily_metric_entity: sensor.ha_fitness_personal_daily_metric_statistics
collection_key: hagym
scope: muscle_groups
metric: strength_volume_kg
unit: kg
limit: 10
chart_mode: stacked_bar
```

Supported scopes:

- `muscle_groups`
- `exercises`
- `equipment`
- `metric_types`

Typical metrics:

- `strength_volume_kg`
- `activity_load_score`
- `duration_minutes`
- `distance_km`
- `calories`
- `steps`

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

HAGym does not depend on Home Assistant Energy internal lazy-loaded date components. The selector is fully owned by HAGym so direct dashboard loads stay stable without unsupported frontend dependencies.

## Official Dashboard Templates

Ready-made templates:

- `dashboards/hagym_energy_style_dashboard_raw.yaml`
  - for direct paste into the normal Home Assistant `Raw configuration editor`
  - starts directly with `views:`
  - does not use a top-level `title`
  - uses `footer.card` for the selector
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

The templates use the selector in the view footer:

```yaml
footer:
  card:
    type: custom:hagym-date-selection
    collection_key: hagym
    placement: inline
    compact: true
    opening_direction: right
    vertical_opening_direction: up
```

This mirrors the native Energy-style footer behavior, but uses the HAGym-owned selector instead of depending on Energy frontend internals.

Use only one HAGym footer selector per view. The supplied templates already follow that rule.

Inline mode is the preferred mode for normal dashboard sections and footer-card usage. `fixed-bottom` is mainly for advanced floating layouts.

## Dashboard Bottom Spacing

If you use `placement: fixed-bottom`, the selector floats above the dashboard content. To avoid the last card being visually covered:

- keep some extra vertical space at the bottom of the last section
- or add a small final spacer card in that view
- or end the view with a lower-priority card that can sit partly behind the footer without hurting usability

For production dashboards, test the last viewport section on both desktop and mobile after adding the footer.

## Example: Simple Inline Use

```yaml
type: vertical-stack
cards:
  - type: custom:hagym-date-selection
    collection_key: hagym
    compact: true
  - type: custom:hagym-period-dashboard-card
    daily_metric_entity: sensor.ha_fitness_personal_daily_metric_statistics
    metric_history_entity: sensor.ha_fitness_personal_weekly_metric_history
    volume_history_entity: sensor.ha_fitness_personal_weekly_volume_history
    collection_key: hagym
    show_embedded_date_selection: false
```

## Troubleshooting

- If Home Assistant says `Custom element doesn't exist`, do a hard browser refresh and reload the companion app view.
- Open the resource URLs directly in the browser, for example:
  - `/hagym_static/hagym-stacked-history-card.js`
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
