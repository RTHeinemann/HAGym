# NFC Workflow (Phase 1.5 YAML Examples)

## Goal

Tap an NFC tag to start/select an exercise and prepare set entry with no cloud dependency.

## Behavior

Each NFC automation should:

1. Start workout if none is active.
2. Set `input_select.fitness_active_exercise` to the tapped exercise.
3. Clear `input_text.fitness_set_notes`.
4. Cancel `timer.fitness_rest_timer`.
5. Log the action to Logbook.

## Placeholder NFC Tag IDs

- `REPLACE_WITH_BENCH_PRESS_TAG_ID`
- `REPLACE_WITH_SQUAT_TAG_ID`
- `REPLACE_WITH_ROW_TAG_ID`

## Example Automations

See [`examples/nfc_automations.yaml`](../examples/nfc_automations.yaml) for:

- NFC Bench Press starts/selects Bench Press
- NFC Squat starts/selects Squat
- NFC Row starts/selects Row

## Multi-User Direction

Implementation is currently single-user helper based. For multi-user expansion, map NFC tag context plus user presence/device to user-specific workout state and analytics entities.
