# Contributing to HAGym

## Scope

Keep changes modular, Home Assistant-native, and local-first.

## Guidelines

- Prefer YAML-first solutions in early phases.
- Follow `fitness_*` entity naming.
- Avoid direct recorder DB modifications.
- Use HA-native helpers, template sensors, utility_meter, scripts, and automations.
- Keep architecture multi-user ready (avoid permanent single-user assumptions).

## Development Flow

1. Make focused, minimal changes.
2. Update docs when behavior or architecture changes.
3. Validate Home Assistant config before opening PR.
4. Include dashboard screenshots for UI changes.

## Pull Request Checklist

- [ ] Change is scoped and minimal
- [ ] Naming conventions followed (`fitness_*`)
- [ ] Docs updated
- [ ] Config validated
- [ ] No cloud dependency introduced
