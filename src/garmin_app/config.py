"""Paths, constants and the chart palette."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("GARMIN_APP_DATA", ROOT / "data"))
CACHE_DIR = DATA_DIR / "cache"
TOKEN_DIR = DATA_DIR / "tokens"
REPORT_DIR = ROOT / "reports"
SAVED_TOKENS = TOKEN_DIR / "default"  # only written with "Remember me"
SAVED_META = SAVED_TOKENS / "meta.json"

# Polite pacing between uncached Garmin requests (seconds).
REQUEST_PAUSE = float(os.getenv("GARMIN_REQUEST_PAUSE", "0.35"))
# Days that are still "live" and get re-fetched (today, yesterday).
LIVE_DAYS = 2
# Cached activity list for the current year is refreshed after this many seconds.
ACTIVITY_TTL = 3600

# Sport groups. Order is the fixed categorical order: color follows the sport.
SPORT_GROUPS = ["Run", "Bike", "Swim", "Strength", "Walk/Hike", "Other"]
SPORT_COLORS = {
    "Run": "#2a78d6",
    "Bike": "#eb6834",
    "Swim": "#1baf7a",
    "Strength": "#eda100",
    "Walk/Hike": "#e87ba4",
    "Other": "#008300",
}
TYPE_TO_GROUP = {
    "running": "Run",
    "trail_running": "Run",
    "treadmill_running": "Run",
    "track_running": "Run",
    "indoor_running": "Run",
    "ultra_run": "Run",
    "virtual_run": "Run",
    "cycling": "Bike",
    "road_biking": "Bike",
    "mountain_biking": "Bike",
    "gravel_cycling": "Bike",
    "indoor_cycling": "Bike",
    "virtual_ride": "Bike",
    "e_bike_fitness": "Bike",
    "cyclocross": "Bike",
    "lap_swimming": "Swim",
    "open_water_swimming": "Swim",
    "swimming": "Swim",
    "strength_training": "Strength",
    "indoor_cardio": "Strength",
    "hiit": "Strength",
    "walking": "Walk/Hike",
    "hiking": "Walk/Hike",
    "casual_walking": "Walk/Hike",
    "speed_walking": "Walk/Hike",
}

# HR zones as an ordinal blue ramp (Z1 light -> Z5 dark).
ZONE_COLORS = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]
ZONE_NAMES = ["Z1 recovery", "Z2 endurance", "Z3 tempo", "Z4 threshold", "Z5 VO2max"]

STATUS_COLORS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
    "info": "#2a78d6",
}
STATUS_ICONS = {
    "good": ":material/check_circle:",
    "warning": ":material/warning:",
    "serious": ":material/report:",
    "critical": ":material/dangerous:",
    "info": ":material/info:",
}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
