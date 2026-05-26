"""Constants for the HAGym integration."""

DOMAIN = "ha_fitness"

# Config entry keys
CONF_DISPLAY_NAME = "display_name"
CONF_INCLUDED_USER_IDS = "included_user_ids"
DEFAULT_DISPLAY_NAME = "HAGym"

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
SERVICE_ADD_MUSCLE_GROUP = "add_muscle_group"
SERVICE_UPDATE_MUSCLE_GROUP = "update_muscle_group"
SERVICE_DISABLE_MUSCLE_GROUP = "disable_muscle_group"
SERVICE_ASSIGN_MUSCLE_GROUP_TO_EXERCISE = "assign_muscle_group_to_exercise"
SERVICE_REFRESH_MUSCLE_GROUPS = "refresh_muscle_groups"

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
ATTR_MUSCLE_GROUP_ID = "muscle_group_id"
ATTR_BODY_REGION = "body_region"
ATTR_ROLE = "role"
ATTR_WEIGHT_FACTOR = "weight_factor"

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

MUSCLE_ROLE_PRIMARY = "primary"
MUSCLE_ROLE_SECONDARY = "secondary"
MUSCLE_ROLE_STABILIZER = "stabilizer"

DEFAULT_MUSCLE_ROLE_WEIGHT_FACTORS: dict[str, float] = {
    MUSCLE_ROLE_PRIMARY: 1.0,
    MUSCLE_ROLE_SECONDARY: 0.5,
    MUSCLE_ROLE_STABILIZER: 0.25,
}

DEFAULT_MUSCLE_GROUPS: list[dict[str, object]] = [
    {"id": "chest", "name_en": "Chest", "name_de": "Brust", "icon": "mdi:human-male", "body_region": "upper_body", "sort_order": 10},
    {"id": "back", "name_en": "Back", "name_de": "Rücken", "icon": "mdi:human-male", "body_region": "upper_body", "sort_order": 20},
    {"id": "shoulders", "name_en": "Shoulders", "name_de": "Schultern", "icon": "mdi:arm-flex", "body_region": "upper_body", "sort_order": 30},
    {"id": "biceps", "name_en": "Biceps", "name_de": "Bizeps", "icon": "mdi:arm-flex", "body_region": "upper_body", "sort_order": 40},
    {"id": "triceps", "name_en": "Triceps", "name_de": "Trizeps", "icon": "mdi:arm-flex", "body_region": "upper_body", "sort_order": 50},
    {"id": "forearms", "name_en": "Forearms", "name_de": "Unterarme", "icon": "mdi:arm-flex", "body_region": "upper_body", "sort_order": 60},
    {"id": "quadriceps", "name_en": "Quadriceps", "name_de": "Quadrizeps", "icon": "mdi:human-handsup", "body_region": "lower_body", "sort_order": 70},
    {"id": "hamstrings", "name_en": "Hamstrings", "name_de": "Beinbeuger", "icon": "mdi:human-handsup", "body_region": "lower_body", "sort_order": 80},
    {"id": "glutes", "name_en": "Glutes", "name_de": "Gesäß", "icon": "mdi:human-handsup", "body_region": "lower_body", "sort_order": 90},
    {"id": "calves", "name_en": "Calves", "name_de": "Waden", "icon": "mdi:human-handsup", "body_region": "lower_body", "sort_order": 100},
    {"id": "core", "name_en": "Core", "name_de": "Core", "icon": "mdi:ab-testing", "body_region": "torso", "sort_order": 110},
    {"id": "abs", "name_en": "Abs", "name_de": "Bauch", "icon": "mdi:ab-testing", "body_region": "torso", "sort_order": 120},
    {"id": "obliques", "name_en": "Obliques", "name_de": "seitliche Bauchmuskeln", "icon": "mdi:ab-testing", "body_region": "torso", "sort_order": 130},
    {"id": "erector_spinae", "name_en": "Erector Spinae", "name_de": "Rückenstrecker", "icon": "mdi:human-male", "body_region": "upper_body", "sort_order": 140},
    {"id": "traps", "name_en": "Traps", "name_de": "Trapez", "icon": "mdi:human-male", "body_region": "upper_body", "sort_order": 150},
    {"id": "lats", "name_en": "Lats", "name_de": "Latissimus", "icon": "mdi:human-male", "body_region": "upper_body", "sort_order": 160},
    {"id": "rhomboids", "name_en": "Rhomboids", "name_de": "Rhomboiden", "icon": "mdi:human-male", "body_region": "upper_body", "sort_order": 170},
    {"id": "adductors", "name_en": "Adductors", "name_de": "Adduktoren", "icon": "mdi:human-handsup", "body_region": "lower_body", "sort_order": 180},
    {"id": "abductors", "name_en": "Abductors", "name_de": "Abduktoren", "icon": "mdi:human-handsup", "body_region": "lower_body", "sort_order": 190},
]

DEFAULT_EXERCISE_MUSCLE_GROUP_MAP: dict[str, list[dict[str, object]]] = {
    "bench_press": [
        {"muscle_group_id": "chest", "role": MUSCLE_ROLE_PRIMARY, "weight_factor": 1.0},
        {"muscle_group_id": "triceps", "role": MUSCLE_ROLE_SECONDARY, "weight_factor": 0.5},
        {"muscle_group_id": "shoulders", "role": MUSCLE_ROLE_SECONDARY, "weight_factor": 0.35},
    ],
    "deadlift": [
        {"muscle_group_id": "glutes", "role": MUSCLE_ROLE_PRIMARY, "weight_factor": 1.0},
        {"muscle_group_id": "hamstrings", "role": MUSCLE_ROLE_PRIMARY, "weight_factor": 0.8},
        {"muscle_group_id": "erector_spinae", "role": MUSCLE_ROLE_PRIMARY, "weight_factor": 0.8},
        {"muscle_group_id": "traps", "role": MUSCLE_ROLE_SECONDARY, "weight_factor": 0.35},
        {"muscle_group_id": "forearms", "role": MUSCLE_ROLE_SECONDARY, "weight_factor": 0.25},
        {"muscle_group_id": "quadriceps", "role": MUSCLE_ROLE_SECONDARY, "weight_factor": 0.35},
    ],
    "squat": [
        {"muscle_group_id": "quadriceps", "role": MUSCLE_ROLE_PRIMARY, "weight_factor": 1.0},
        {"muscle_group_id": "glutes", "role": MUSCLE_ROLE_PRIMARY, "weight_factor": 0.8},
        {"muscle_group_id": "hamstrings", "role": MUSCLE_ROLE_SECONDARY, "weight_factor": 0.5},
        {"muscle_group_id": "core", "role": MUSCLE_ROLE_STABILIZER, "weight_factor": 0.25},
        {"muscle_group_id": "erector_spinae", "role": MUSCLE_ROLE_STABILIZER, "weight_factor": 0.25},
    ],
    "lat_pulldown": [
        {"muscle_group_id": "lats", "role": MUSCLE_ROLE_PRIMARY, "weight_factor": 1.0},
        {"muscle_group_id": "biceps", "role": MUSCLE_ROLE_SECONDARY, "weight_factor": 0.5},
        {"muscle_group_id": "rhomboids", "role": MUSCLE_ROLE_SECONDARY, "weight_factor": 0.4},
        {"muscle_group_id": "traps", "role": MUSCLE_ROLE_SECONDARY, "weight_factor": 0.3},
    ],
    "row": [
        {"muscle_group_id": "lats", "role": MUSCLE_ROLE_PRIMARY, "weight_factor": 0.8},
        {"muscle_group_id": "rhomboids", "role": MUSCLE_ROLE_PRIMARY, "weight_factor": 0.8},
        {"muscle_group_id": "traps", "role": MUSCLE_ROLE_SECONDARY, "weight_factor": 0.5},
        {"muscle_group_id": "biceps", "role": MUSCLE_ROLE_SECONDARY, "weight_factor": 0.5},
        {"muscle_group_id": "shoulders", "role": MUSCLE_ROLE_SECONDARY, "weight_factor": 0.3},
    ],
    "shoulder_press": [
        {"muscle_group_id": "shoulders", "role": MUSCLE_ROLE_PRIMARY, "weight_factor": 1.0},
        {"muscle_group_id": "triceps", "role": MUSCLE_ROLE_SECONDARY, "weight_factor": 0.5},
        {"muscle_group_id": "chest", "role": MUSCLE_ROLE_STABILIZER, "weight_factor": 0.2},
    ],
    "bicep_curl": [
        {"muscle_group_id": "biceps", "role": MUSCLE_ROLE_PRIMARY, "weight_factor": 1.0},
        {"muscle_group_id": "forearms", "role": MUSCLE_ROLE_SECONDARY, "weight_factor": 0.25},
    ],
    "tricep_pushdown": [
        {"muscle_group_id": "triceps", "role": MUSCLE_ROLE_PRIMARY, "weight_factor": 1.0},
        {"muscle_group_id": "forearms", "role": MUSCLE_ROLE_STABILIZER, "weight_factor": 0.15},
    ],
}
