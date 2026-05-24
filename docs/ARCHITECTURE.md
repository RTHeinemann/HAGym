# Architecture

## Design Goals

- Home Assistant-native first
- Modular package-based YAML
- Privacy/local ownership
- Future multi-user support

## Modules

- `packages/fitness_helpers.yaml` - helper entities
- `packages/fitness_workout.yaml` - workout flow scripts/automations
- `packages/fitness_statistics.yaml` - template sensors + utility meters
- `packages/fitness_metadata.yaml` - metadata and user model scaffolding

## Entity Naming

All entities use `fitness_*` prefix, e.g.:

- `input_select.fitness_active_exercise`
- `input_number.fitness_input_weight`
- `sensor.fitness_pr_bench_press`
- `timer.fitness_rest_timer`

## Multi-User Compatibility Strategy

MVP writes to global helpers but keeps data model future-ready through namespaced structures in attributes/examples:

```yaml
fitness:
  users:
    user_id:
      profile:
        display_name: "Alex"
      volume:
        bench_press: 0
```

## Technical Constraints

- Do not write directly to HA recorder DB.
- Prefer helper + template + utility_meter composition.
- Keep migration path to SQLite and custom integration explicit.
