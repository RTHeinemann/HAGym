# Migration from YAML to Native Integration

This document describes the migration path from the YAML-based prototype
(`/packages`) to the native Home Assistant custom integration (`custom_components/ha_fitness`).

## Current State (Phase 1.7)

| Feature | YAML Packages | Native Integration |
|---------|:---:|:---:|
| Workout status sensor | ✅ | ✅ |
| Start / Finish workout buttons | ✅ | ✅ |
| Exercise selection | ✅ | ✅ (`select.ha_fitness_active_exercise`) |
| Weight / Reps input | ✅ | ✅ (`number.ha_fitness_weight`, `number.ha_fitness_reps`) |
| Notes input | ✅ | ✅ (`text.ha_fitness_notes`) |
| Save set (button + service) | ✅ | ✅ |
| Last set sensor | ✅ | ✅ |
| Current set number sensor | ✅ | ✅ |
| Set volume sensor | ✅ | ✅ |
| Active workout summary sensor | ✅ | ✅ |
| Persistence across HA restart | ✅ | ❌ planned |
| Exercise history | ✅ | ❌ planned |
| PR tracking | ✅ | ❌ planned |
| Volume statistics | ✅ | ❌ planned |
| Recovery tracking | ✅ | ❌ planned |
| NFC / QR workflow | ✅ | ❌ planned |
| SQLite persistence | ❌ planned | ❌ planned |
| Config UI (Settings → D&S) | ❌ | ✅ |
| HACS installable | ❌ | ✅ |

## Native Workout Flow

The Phase 1.7 integration supports a complete minimal workout flow:

1. **Start Workout** – press `button.ha_fitness_start_workout`
2. **Select Exercise** – choose from `select.ha_fitness_active_exercise`
3. **Enter Weight** – set `number.ha_fitness_weight`
4. **Enter Reps** – set `number.ha_fitness_reps`
5. **Optional Notes** – fill `text.ha_fitness_notes`
6. **Press Save Set** – press `button.ha_fitness_save_set`
7. **See Last Set and Summary** – check `sensor.ha_fitness_last_set` and `sensor.ha_fitness_active_workout_summary`
8. **Finish Workout** – press `button.ha_fitness_finish_workout`

## Current Limitations

- **No persistence across HA restart** – all runtime state (set number, last set, etc.) is reset on restart.
- **No per-exercise PR tracking** – planned for a future phase.
- **No workout volume history** – planned together with SQLite storage.
- **No SQLite** – lightweight in-memory state only.
- **YAML prototype remains more complete for analytics** – use YAML packages for volume history, PRs, and statistics.

## Migration Roadmap

### Phase 1.7 – Native entity migration start (current)
- Native exercise selection (`select`), weight/reps inputs (`number`), notes (`text`).
- Save set button with validation and persistent notification on error.
- Extended sensors: active exercise, set number, last set, volume, summary.
- Improved `save_set` service with strict validation.

### Phase 2 – Persistence
- Introduce SQLite-backed storage via a custom database helper.
- Persist workouts and sets across HA restarts.
- Implement exercise catalogue as a native data model.

### Phase 3 – History and statistics
- Migrate workout history templates to native sensors.
- Implement PR tracking in the coordinator.
- Migrate weekly/monthly/yearly statistics to native statistics entries.

### Phase 4 – Advanced workflows
- Integrate NFC/QR automation triggers as integration events.
- Multi-user support via multiple config entries.
- Recovery analytics as computed sensors.

## Running Both in Parallel

You can run the YAML packages and the native integration side-by-side during
migration. They use separate entity domains (`fitness_*` for YAML, `ha_fitness_*`
for the integration) and do not interfere with each other.

## Removing YAML Packages

Once all features have been migrated to the native integration, you can safely:

1. Remove the package files from your Home Assistant `packages/` directory.
2. Remove `input_number`, `input_text`, and `input_boolean` helpers created by the packages.
3. Remove any Lovelace cards that reference `fitness_*` entities and replace them with `ha_fitness_*` equivalents.
