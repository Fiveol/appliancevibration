"""Constants for the ApplianceVibration integration."""

from homeassistant.const import Platform

DOMAIN = "appliancevibration"

CONF_ICON = "icon"

DEFAULT_NAME = "Appliance Vibration"
DEFAULT_ICON = "mdi:vibrate"

# Sidebar panel
PANEL_URL_PATH = DOMAIN
WEBCOMPONENT_NAME = "appliance-vibration-panel"
PANEL_FILENAME = "panel.js"
PANEL_STATIC_PATH = f"/api/{DOMAIN}/panel"

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN

# Entity keys (used for unique ids, translation keys and slugs)
KEY_CYCLE = "cycle"
KEY_PROGRAM = "program"
KEY_LEVEL = "level"
KEY_DURATION = "duration"
KEY_COUNT = "count"
KEY_STAGE = "stage"
KEY_STAGE_DURATION = "stage_duration"
KEY_TIME_REMAINING = "time_remaining"

ENTITY_KEYS = [
    KEY_CYCLE,
    KEY_PROGRAM,
    KEY_LEVEL,
    KEY_DURATION,
    KEY_COUNT,
    KEY_STAGE,
    KEY_STAGE_DURATION,
    KEY_TIME_REMAINING,
]

# Default device settings
DEFAULT_THRESHOLD = 0.2
DEFAULT_START_DELAY = 10
DEFAULT_END_DELAY = 60
DEFAULT_MIN_CONFIDENCE = 0.7
DEFAULT_MIN_DURATION = 300  # seconds; runs shorter than this are discarded

SETTING_THRESHOLD = "threshold"
SETTING_START_DELAY = "start_delay"
SETTING_END_DELAY = "end_delay"
SETTING_MIN_CONFIDENCE = "min_confidence"
SETTING_MIN_DURATION = "min_duration"

# Device storage keys
ATTR_DEVICES = "devices"
DEV_ID = "id"
DEV_NAME = "name"
DEV_SLUG = "slug"
DEV_ENTITIES = "entities"
DEV_SETTINGS = "settings"
DEV_PROGRAMS = "programs"
DEV_CYCLES = "cycles"
DEV_ENT_IDS = "entity_ids"  # entity ids of created HA entities
DEV_MONITOR = "monitor"  # runtime: DeviceMonitor

# Program keys
PROG_NAME = "name"
PROG_COLOR = "color"
PROG_SAMPLES = "samples"
PROG_STATS = "stats"

# Cycle keys
CYC_ID = "id"
CYC_STARTED = "started"
CYC_ENDED = "ended"
CYC_DURATION = "duration"
CYC_MAG_MEAN = "magnitude_mean"
CYC_MAG_MAX = "magnitude_max"
CYC_MAG_STD = "magnitude_std"
CYC_ACTIVE_RATIO = "active_ratio"
CYC_PROGRAM_ID = "program_id"
CYC_CONFIDENCE = "confidence"
CYC_LABELED = "labeled"
CYC_STAGES = "stages"

# Cycle features used for classification
FEATURES = [CYC_DURATION, CYC_MAG_MEAN, CYC_MAG_MAX, CYC_MAG_STD]

# Keep the last N cycles per device
MAX_CYCLES = 100

# Program color palette used by the panel
PROGRAM_COLORS = [
    "#1e88e5",
    "#43a047",
    "#f4511e",
    "#8e24aa",
    "#00897b",
    "#e53935",
    "#6d4c41",
    "#fb8c00",
    "#3949ab",
    "#00acc1",
]

UNCLASSIFIED = "Unclassified"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
