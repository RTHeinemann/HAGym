"""Constants for the HA Fitness Tracker integration."""

DOMAIN = "ha_fitness"

# Config entry keys
CONF_DISPLAY_NAME = "display_name"
CONF_INCLUDED_USER_IDS = "included_user_ids"
DEFAULT_DISPLAY_NAME = "HA Fitness Tracker"

# Workout states
STATE_READY = "ready"
STATE_ACTIVE = "active"

# Multi-user defaults
LEGACY_USER_ID = "legacy"
LEGACY_USER_NAME = "Legacy / Pre-Multi-User Data"

# Service names
SERVICE_START_WORKOUT = "start_workout"
SERVICE_FINISH_WORKOUT = "finish_workout"
SERVICE_SAVE_SET = "save_set"
SERVICE_SAVE_CURRENT_SET = "save_current_set"
SERVICE_REFRESH_STATISTICS = "refresh_statistics"
SERVICE_EXPORT_DATA = "export_data"
SERVICE_SELECT_USER = "select_user"
SERVICE_REFRESH_USERS = "refresh_users"

# Service field names
ATTR_EXERCISE = "exercise"
ATTR_WEIGHT = "weight"
ATTR_REPS = "reps"
ATTR_NOTES = "notes"
ATTR_USER_ID = "user_id"

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
