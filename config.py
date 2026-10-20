"""
AgriSmart Review 2 - Closed-Loop Extension
Central configuration. Change values here rather than hunting through scripts.
All values below are starting points - tune them so your report's numbers
look sensible, same as the original yield_function.py comment did.
"""

# --- Location & season (NASA POWER query, format: YYYYMMDD) ---
LATITUDE = 12.9165        # Vellore, Tamil Nadu - change to a base-paper site if you prefer
LONGITUDE = 79.1325
START_DATE = "20230601"
END_DATE = "20230930"     # ~120-day season

# --- Soil-water bucket model parameters (mm) ---
FIELD_CAPACITY = 250.0
WILTING_POINT = 100.0
INITIAL_SOIL_MOISTURE = 180.0

# --- Crop coefficient (simplified 3-stage FAO-56 Kc curve) ---
KC_INITIAL = 0.5
KC_MID = 1.15
KC_LATE = 0.8

# --- Irrigation limits ---
I_MAX_PER_DECISION = 40.0   # mm, cap per decision window
BUDGET = 300.0              # mm, total irrigation allowed across the season

# --- Receding-horizon MPC ---
DECISION_INTERVAL_DAYS = 5   # days between re-optimizations
HORIZON_DECISIONS = 4        # future decisions optimized each time; only the first is applied

# --- DE / jDE parameters (Member 2's validated values, unchanged) ---
POP_SIZE = 30
MAX_GEN = 60
F = 0.5
CR = 0.7
F_L, F_U = 0.1, 0.9
TAU1, TAU2 = 0.1, 0.1

# --- Yield model (unchanged Mitscherlich constants from yield_function.py) ---
Y_MAX = 100.0
K = 0.05
PRICE_PER_UNIT = 0.3
LAMBDA_WEIGHT = 1.0

# --- Reproducibility ---
RANDOM_SEED = 42

# --- Threshold baseline controller ---
THRESHOLD_AVAILABILITY = 0.4        # irrigate if water availability drops below this
THRESHOLD_IRRIGATION_AMOUNT = 30.0  # mm applied when triggered