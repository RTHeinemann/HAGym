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
SERVICE_ADD_EXERCISE = "add_exercise"
SERVICE_UPDATE_EXERCISE = "update_exercise"
SERVICE_DISABLE_EXERCISE = "disable_exercise"
SERVICE_REFRESH_EXERCISES = "refresh_exercises"
SERVICE_SELECT_EQUIPMENT = "select_equipment"

# Service field names
ATTR_EXERCISE = "exercise"
ATTR_EXERCISE_ID = "exercise_id"
ATTR_WEIGHT = "weight"
ATTR_REPS = "reps"
ATTR_NOTES = "notes"
ATTR_USER_ID = "user_id"
ATTR_NAME_EN = "name_en"
ATTR_NAME_DE = "name_de"
ATTR_MUSCLE_GROUP = "muscle_group"
ATTR_EQUIPMENT = "equipment"
ATTR_EQUIPMENT_ID = "equipment_id"
ATTR_DESCRIPTION = "description"
ATTR_ICON = "icon"
ATTR_LOCATION = "location"
ATTR_ENABLED = "enabled"
ATTR_SORT_ORDER = "sort_order"

# Stable default exercise IDs (also used by existing per-exercise sensors)
EXERCISE_IDS: list[str] = [
    "bench_press",
    "squat",
    "deadlift",
    "shoulder_press",
    "row",
    "lat_pulldown",
    "bicep_curl",
    "tricep_pushdown",
]

DEFAULT_EXERCISES: list[dict[str, object]] = [
    {
        "id": "bench_press",
        "name_en": "Bench Press",
        "name_de": "Bankdrücken",
        "muscle_group": "chest",
        "equipment": "barbell",
        "sort_order": 10,
    },
    {
        "id": "squat",
        "name_en": "Squat",
        "name_de": "Kniebeuge",
        "muscle_group": "legs",
        "equipment": "barbell",
        "sort_order": 20,
    },
    {
        "id": "deadlift",
        "name_en": "Deadlift",
        "name_de": "Kreuzheben",
        "muscle_group": "posterior_chain",
        "equipment": "barbell",
        "sort_order": 30,
    },
    {
        "id": "shoulder_press",
        "name_en": "Shoulder Press",
        "name_de": "Schulterdrücken",
        "muscle_group": "shoulders",
        "equipment": "barbell",
        "sort_order": 40,
    },
    {
        "id": "row",
        "name_en": "Row",
        "name_de": "Rudern",
        "muscle_group": "back",
        "equipment": "machine",
        "sort_order": 50,
    },
    {
        "id": "lat_pulldown",
        "name_en": "Lat Pulldown",
        "name_de": "Latzug",
        "muscle_group": "back",
        "equipment": "cable",
        "sort_order": 60,
    },
    {
        "id": "bicep_curl",
        "name_en": "Bicep Curl",
        "name_de": "Bizepscurls",
        "muscle_group": "biceps",
        "equipment": "dumbbell",
        "sort_order": 70,
    },
    {
        "id": "tricep_pushdown",
        "name_en": "Tricep Pushdown",
        "name_de": "Trizepsdrücken",
        "muscle_group": "triceps",
        "equipment": "cable",
        "sort_order": 80,
    },
]

DEFAULT_EQUIPMENT: list[dict[str, object]] = [
    {
        "id": "bench_station",
        "name": "Bench Station",
        "description": None,
        "icon": "mdi:bench",
        "location": None,
        "enabled": True,
        "sort_order": 10,
    },
    {
        "id": "cable_tower",
        "name": "Cable Tower",
        "description": None,
        "icon": "mdi:pulley",
        "location": None,
        "enabled": True,
        "sort_order": 20,
    },
    {
        "id": "squat_rack",
        "name": "Squat Rack",
        "description": None,
        "icon": "mdi:weight-lifter",
        "location": None,
        "enabled": True,
        "sort_order": 30,
    },
    {
        "id": "dumbbell_area",
        "name": "Dumbbell Area",
        "description": None,
        "icon": "mdi:dumbbell",
        "location": None,
        "enabled": True,
        "sort_order": 40,
    },
    {
        "id": "rowing_station",
        "name": "Row Station",
        "description": None,
        "icon": "mdi:rowing",
        "location": None,
        "enabled": True,
        "sort_order": 50,
    },
]

DEFAULT_EXERCISE_EQUIPMENT_MAP: dict[str, str] = {
    "bench_press": "bench_station",
    "lat_pulldown": "cable_tower",
    "tricep_pushdown": "cable_tower",
    "squat": "squat_rack",
    "row": "rowing_station",
    "bicep_curl": "dumbbell_area",
    "deadlift": "squat_rack",
    "shoulder_press": "squat_rack",
}
