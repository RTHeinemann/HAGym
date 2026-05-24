# QR Workflow (Planned + YAML-Compatible)

## Goal

Scan a QR code from mobile to jump directly to an exercise/workout action.

## Flow

1. QR deep-link opens Home Assistant action endpoint/view.
2. Exercise context is parsed from QR payload.
3. Active exercise helper updates.
4. Dashboard focus switches to current-set entry.

## Future Multi-User Extension

- Resolve current mobile device/user to `user_id`.
- Route to user-specific training plan and stats views.
