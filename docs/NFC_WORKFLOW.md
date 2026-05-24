# NFC Workflow (Planned + YAML-Compatible)

## Goal

Tap an NFC tag to start/select an exercise and move workout flow forward.

## Flow

1. User taps exercise NFC tag.
2. Automation maps NFC tag -> exercise key.
3. `input_select.fitness_active_exercise` is set.
4. Rest timer and set-entry helpers are prepared.
5. User submits set via save-set script.

## Future Multi-User Extension

- Map `tag_id + user presence` to `user_id` ownership.
- Persist set logs as `fitness.volume[user_id][exercise]`.
- Support user-specific dashboards and PR sensors.
