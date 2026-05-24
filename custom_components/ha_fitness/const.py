"""Constants for the HA Fitness Tracker integration."""

DOMAIN = "ha_fitness"

# Config entry keys
CONF_DISPLAY_NAME = "display_name"
DEFAULT_DISPLAY_NAME = "HA Fitness Tracker"

# Workout states
STATE_READY = "ready"
STATE_ACTIVE = "active"

# Service names
SERVICE_START_WORKOUT = "start_workout"
SERVICE_FINISH_WORKOUT = "finish_workout"
SERVICE_SAVE_SET = "save_set"

# Service field names
ATTR_EXERCISE = "exercise"
ATTR_WEIGHT = "weight"
ATTR_REPS = "reps"
ATTR_NOTES = "notes"

# Available exercises for the select entity
EXERCISES: list[str] = [
    "Bench Press",
    "Squat",
    "Deadlift",
    "Shoulder Press",
    "Row",
    "Lat Pulldown",
    "Bicep Curl",
    "Tricep Pushdown",
]
