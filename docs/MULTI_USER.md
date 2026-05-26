# HAGym Multi-User Tracking

## Overview

HAGym supports Home Assistant user-aware workout attribution.

- Attribution source: `call.context.user_id`
- No parsing or mutation of `/config/.storage/auth`
- No direct writes to Home Assistant recorder tables

## Data Model

- `users` table stores known HAGym users.
- `workouts.user_id` links workouts to users.
- `set_logs.user_id` links saved sets to users.

Legacy data from pre-multi-user versions is preserved and assigned to:

- `user_id = "legacy"`
- Display name: `Legacy / Pre-Multi-User Data`

## Personal vs Household Statistics

Personal statistics use:

- selected user id (if set), otherwise
- current context user id, otherwise
- `legacy`

Household statistics use:

- configured `included_user_ids` from options flow, or
- all enabled users if no explicit list is configured

## Dashboard Recommendations

For accurate per-user attribution, prefer service-based Lovelace actions:

- `ha_fitness.start_workout`
- `ha_fitness.save_current_set`
- `ha_fitness.finish_workout`

Direct entity button presses are kept for compatibility, but Home Assistant may not always expose a reliable user context in that path.

## Export

`ha_fitness.export_data` includes:

- users
- global stats
- personal stats
- household stats
- recent sets including `user_id`
