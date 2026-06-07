"""
config.py — single source of truth for the OP26 pipeline.

All paths, constants, and thresholds live here so the whole project is
reproducible and every magic number is documented in one place.

Raw data location resolution (in priority order):
  1. environment variable  OP26_DATA   (e.g. export OP26_DATA=/path/to/files)
  2. ./data_raw  next to this file      (drop the OpenProject files here)
A clear FileNotFoundError is raised at load time if a file is missing.
"""
from pathlib import Path
import os

# --- paths -----------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("OP26_DATA", PROJECT_ROOT / "data_raw"))
OUTPUT_DIR = PROJECT_ROOT / "outputs"
FIG_DIR = PROJECT_ROOT / "figures"
OUTPUT_DIR.mkdir(exist_ok=True)
FIG_DIR.mkdir(exist_ok=True)

# --- raw file names --------------------------------------------------------
ACN_FILE = "acndata_sessions_json.xlsx"
F_OCCUPANCY = "occupancy.csv"
F_VOLUME = "volume.csv"
F_DURATION = "duration.csv"
F_PRICE = "price.csv"
F_INFO = "information.csv"
F_STATIONS = "stations.csv"
F_ADJ = "adj.csv"
F_DISTANCE = "distance.csv"
F_TIME = "time.csv"

# --- temporal grid (UrbanEV) ----------------------------------------------
INTERVAL_MIN = 5                 # raw resolution of UrbanEV matrices
INTERVALS_PER_HOUR = 60 // INTERVAL_MIN   # = 12

# --- utilization / pricing thresholds (from the brief) ---------------------
SATURATION_THRESHOLD = 0.95      # occupancy/piles at/above this == "saturated" (queue proxy)
UTIL_SURGE = 0.80                # brief: surge when utilization > 80%
UTIL_DISCOUNT = 0.30             # brief: discount when utilization < 30%

# --- ACN cleaning rules ----------------------------------------------------
ACN_TZ = "America/Los_Angeles"   # Caltech local time (raw timestamps are GMT)
ACN_MIN_KWH = 0.5                # implausibly tiny sessions removed
ACN_MAX_DURATION_HR = 48.0       # implausibly long dwell removed (documented cap)
ACN_MAX_POWER_KW = 350.0         # above fastest real chargers -> artifact, flagged + nulled
ACN_DATETIME_FMT = "%a, %d %b %Y %H:%M:%S %Z"   # RFC-2822 (explicit; inference is unreliable here)

# --- misc ------------------------------------------------------------------
RANDOM_SEED = 42

# baseline flat tariff for the India narrative (illustrative framing only;
# all reported metrics are unit-invariant ratios — see ASSUMPTIONS.md)
INR_FLAT_BASELINE = 15.0
