# QR Workflow (Phase 1.5 YAML Examples)

## Goal

Scan a QR code to trigger a local Home Assistant webhook that starts/selects an exercise quickly.

## Behavior

Each QR webhook automation should:

1. Start workout if none is active.
2. Set `input_select.fitness_active_exercise` to the scanned exercise.
3. Clear `input_text.fitness_set_notes`.
4. Cancel `timer.fitness_rest_timer`.
5. Log the action to Logbook.

## Example Webhooks

- `fitness_qr_bench_press`
- `fitness_qr_squat`
- `fitness_qr_row`

## Example QR URLs

- `https://YOUR_HA_URL/api/webhook/fitness_qr_bench_press`
- `https://YOUR_HA_URL/api/webhook/fitness_qr_squat`
- `https://YOUR_HA_URL/api/webhook/fitness_qr_row`

## Example Automations

See [`examples/qr_webhook_automations.yaml`](../examples/qr_webhook_automations.yaml).

## Multi-User Direction

Implementation is currently single-user helper based. Future multi-user behavior should resolve the scanning device/user and route to user-specific workout and statistics entities.
