"""Constants for Smart Climate integration."""

DOMAIN = "smart_climate"

# Platforms
PLATFORM_CLIMATE = "climate"
PLATFORM_SENSOR = "sensor"
PLATFORM_NUMBER = "number"
PLATFORM_SELECT = "select"

# ---------------------------------------------------------------------------
# Config entry keys
# ---------------------------------------------------------------------------
CONF_HEATER = "heater"
CONF_COOLER = "cooler"
CONF_SENSOR = "target_sensor"
CONF_SENSOR_OUTSIDE = "outside_sensor"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_TARGET_TEMP = "target_temp"
CONF_COLD_TOLERANCE = "cold_tolerance"
CONF_HOT_TOLERANCE = "hot_tolerance"
CONF_KEEP_ALIVE = "keep_alive"
CONF_INITIAL_HVAC_MODE = "initial_hvac_mode"
CONF_PRECISION = "precision"
CONF_ALGORITHM = "algorithm"
CONF_PID_KP = "pid_kp"
CONF_PID_KI = "pid_ki"
CONF_PID_KD = "pid_kd"
CONF_MIN_CYCLE_DURATION = "min_cycle_duration"
CONF_AC_MODE = "ac_mode"
CONF_AC_IDLE_MODE = "ac_idle_mode"

# AC idle mode opties
AC_IDLE_OFF = "off"           # Airco volledig uit (standaard)
AC_IDLE_FAN_ONLY = "fan_only" # Ventilator aan, compressor uit
DEFAULT_AC_IDLE_MODE = AC_IDLE_OFF

# Presets
CONF_PRESET_COMFORT_TEMP = "preset_comfort_temp"
CONF_PRESET_ECO_TEMP = "preset_eco_temp"
CONF_PRESET_SLEEP_TEMP = "preset_sleep_temp"
CONF_PRESET_AWAY_TEMP = "preset_away_temp"
CONF_PRESET_BOOST_TEMP = "preset_boost_temp"
CONF_BOOST_DURATION = "boost_duration"

# Presence
CONF_PRESENCE_SENSORS = "presence_sensors"

# Window detection
CONF_WINDOW_DETECTION = "window_detection"
CONF_WINDOW_SENSOR = "window_sensor"           # binary_sensor entiteit (directe raamdetekie)
CONF_WINDOW_TEMP_DROP = "window_temp_drop"
CONF_WINDOW_TEMP_DROP_TIME = "window_temp_drop_time"
CONF_WINDOW_OPEN_DURATION = "window_open_duration"

# Weather compensation
CONF_WEATHER_COMPENSATION = "weather_compensation"
CONF_WEATHER_SLOPE = "weather_slope"
CONF_WEATHER_OUTSIDE_REF = "weather_outside_ref"

# Energy
CONF_HEATER_WATT = "heater_watt"
CONF_COOLER_WATT = "cooler_watt"

# Schedule
CONF_SCHEDULE = "schedule"

# Learning / Early Start
CONF_LEARNING_ENABLED = "learning_enabled"
CONF_EARLY_START = "early_start"

# Cascade (primaire + secundaire verwarming/koeling)
CONF_CASCADE_ENABLED = "cascade_enabled"
CONF_CASCADE_PRIMARY_HEATER = "cascade_primary_heater"
CONF_CASCADE_PRIMARY_COOLER = "cascade_primary_cooler"
CONF_CASCADE_TIMEOUT = "cascade_timeout_min"
CONF_CASCADE_TEMP_THRESHOLD = "cascade_temp_threshold"
CONF_CASCADE_DEACTIVATE_DELAY = "cascade_deactivate_delay_min"
CONF_CASCADE_INSTANT_THRESHOLD = "cascade_instant_threshold"  # °C tekort → meteen secundaire

# Koeling blokkeren bij lage buitentemperatuur
CONF_COOL_BLOCK_OUTSIDE_TEMP = "cool_block_outside_temp"

# Voorspellende koelblokkering (weather entity + forecast)
CONF_WEATHER_ENTITY = "weather_entity"
CONF_FORECAST_COOL_BLOCK_THRESHOLD = "forecast_cool_block_threshold"
CONF_FORECAST_COOL_BLOCK_HOURS = "forecast_cool_block_hours"

# Geleidelijke preset-overgang (ramp)
CONF_TEMP_RAMP = "temp_ramp_enabled"
CONF_TEMP_RAMP_STEP = "temp_ramp_step"          # °C per stap
CONF_TEMP_RAMP_INTERVAL = "temp_ramp_interval"  # minuten per stap

# Persistent notification bij vertraging
CONF_NOTIFY_ON_DELAY = "notify_on_delay"
CONF_NOTIFY_DELAY_MIN = "notify_delay_min"
CONF_NOTIFY_SERVICE = "notify_service"       # optionele mobiele push-service

# Vorstbeveiliging
CONF_FROST_PROTECTION_TEMP = "frost_protection_temp"

# Sensorfailsafe
CONF_SENSOR_TIMEOUT_MIN = "sensor_timeout_min"

# Vochtcomfortcorrectie
CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_HUMIDITY_REF = "humidity_ref"
CONF_HUMIDITY_FACTOR = "humidity_factor"

# Prijsgestuurde setback
CONF_ENERGY_PRICE_SENSOR = "energy_price_sensor"
CONF_ENERGY_PRICE_THRESHOLD = "energy_price_threshold"
CONF_ENERGY_PRICE_SETBACK = "energy_price_setback"

# Hold-modus
CONF_HOLD_TEMP = "hold_temp"       # intern, niet in config flow

# Seizoensdetectie
CONF_AUTO_MODE = "auto_mode"
CONF_AUTO_MODE_COOL_THRESHOLD = "auto_mode_cool_threshold"
CONF_AUTO_MODE_HEAT_THRESHOLD = "auto_mode_heat_threshold"

# HA Calendar koppeling
CONF_VACATION_CALENDAR = "vacation_calendar"

# Pump
CONF_PUMP_ENTITY = "pump_entity"
CONF_PUMP_ZONE_ENTITIES = "pump_zone_entities"
CONF_PUMP_ANTI_SEIZE_INTERVAL = "pump_anti_seize_interval_h"
CONF_PUMP_ANTI_SEIZE_DURATION = "pump_anti_seize_duration_min"
CONF_PUMP_POST_HEAT_DELAY = "pump_post_heat_delay_min"
CONF_PUMP_MIN_RUN_TIME = "pump_min_run_time_sec"
CONF_PUMP_EXERCISE_TIME = "pump_exercise_time"

# Multi-split (gedeelde buitenunit)
CONF_MULTISPLIT_GROUP = "multisplit_group"
CONF_MULTISPLIT_PRIORITY_TEMP = "multisplit_priority_temp"
CONF_MULTISPLIT_SWITCH_MARGIN = "multisplit_switch_margin"
DEFAULT_MULTISPLIT_PRIORITY_TEMP = 3.0   # °C — afwijking voor directe voorrang
DEFAULT_MULTISPLIT_SWITCH_MARGIN = 1.0   # °C — minimaal verschil om van modus te wisselen

# ---------------------------------------------------------------------------
# Algorithms
# ---------------------------------------------------------------------------
ALGORITHM_HYSTERESIS = "hysteresis"
ALGORITHM_PID = "pid"
ALGORITHM_PREDICTIVE = "predictive"
ALGORITHMS = [ALGORITHM_HYSTERESIS, ALGORITHM_PID, ALGORITHM_PREDICTIVE]

# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------
PRESET_COMFORT = "comfort"
PRESET_ECO = "eco"
PRESET_SLEEP = "sleep"
PRESET_AWAY = "away"
PRESET_BOOST = "boost"
PRESET_SCHEDULE = "schedule"
PRESET_NONE = "none"

PRESETS = [PRESET_COMFORT, PRESET_ECO, PRESET_SLEEP, PRESET_AWAY, PRESET_BOOST, PRESET_SCHEDULE]

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_TOLERANCE = 0.3
DEFAULT_MIN_TEMP = 7.0
DEFAULT_MAX_TEMP = 35.0
DEFAULT_TARGET_TEMP = 20.0
DEFAULT_PRECISION = 0.1
DEFAULT_ALGORITHM = ALGORITHM_HYSTERESIS
DEFAULT_PID_KP = 1.0
DEFAULT_PID_KI = 0.1
DEFAULT_PID_KD = 0.5
DEFAULT_KEEP_ALIVE = 30
DEFAULT_MIN_CYCLE_DURATION = 10

DEFAULT_PRESET_COMFORT = 20.0
DEFAULT_PRESET_ECO = 17.0
DEFAULT_PRESET_SLEEP = 16.0
DEFAULT_PRESET_AWAY = 12.0
DEFAULT_PRESET_BOOST = 24.0
DEFAULT_BOOST_DURATION = 60  # minutes

DEFAULT_WINDOW_TEMP_DROP = 1.5   # °C
DEFAULT_WINDOW_TEMP_DROP_TIME = 5  # minutes
DEFAULT_WINDOW_OPEN_DURATION = 20  # minutes
DEFAULT_COOL_BLOCK_OUTSIDE_TEMP = 16.0   # °C — koel niet als buiten al koud
DEFAULT_FORECAST_COOL_BLOCK_THRESHOLD = 15.0  # °C — min. voorspeld → blokkeer koelen
DEFAULT_FORECAST_COOL_BLOCK_HOURS = 12        # uren vooruit kijken
DEFAULT_CASCADE_INSTANT_THRESHOLD = 3.0  # °C tekort → meteen secundaire inschakelen
DEFAULT_TEMP_RAMP_STEP = 0.5             # °C per ramp-stap
DEFAULT_TEMP_RAMP_INTERVAL = 5           # minuten per ramp-stap
DEFAULT_NOTIFY_DELAY_MIN = 60            # minuten wachten voor notificatie
DEFAULT_FROST_PROTECTION_TEMP = 5.0      # °C — vorst drempel
DEFAULT_SENSOR_TIMEOUT_MIN = 30          # minuten — sensor mag maximaal stil zijn
DEFAULT_HUMIDITY_REF = 50.0              # % — referentievochtigheid
DEFAULT_HUMIDITY_FACTOR = 0.05           # °C aanpassing per % afwijking
DEFAULT_ENERGY_PRICE_THRESHOLD = 0.25    # EUR/kWh — drempel voor dure energie
DEFAULT_ENERGY_PRICE_SETBACK = 2.0       # °C — setback bij dure energie
DEFAULT_AUTO_MODE_COOL_THRESHOLD = 22.0  # °C buiten → switch naar koelen
DEFAULT_AUTO_MODE_HEAT_THRESHOLD = 18.0  # °C buiten → switch naar verwarmen

DEFAULT_WEATHER_SLOPE = 0.5
DEFAULT_WEATHER_OUTSIDE_REF = 15.0

DEFAULT_HEATER_WATT = 1500
DEFAULT_COOLER_WATT = 1000

# Learning
EMA_ALPHA = 0.3          # weight of newest observation in EMA update
DEFAULT_LEARNING_ENABLED = True
DEFAULT_EARLY_START = True

# Cascade
DEFAULT_CASCADE_TIMEOUT = 30          # minuten wachten voor secundair inschakelt
DEFAULT_CASCADE_TEMP_THRESHOLD = 1.5  # °C tekort t.o.v. doel om secundair te activeren
DEFAULT_CASCADE_DEACTIVATE_DELAY = 10 # minuten secundair nog aan na bereiken doel

# Notification
NOTIFICATION_ID_PREFIX = "smart_climate_delay_"

# Services (hold-modus)
SERVICE_SET_HOLD = "set_hold"
SERVICE_CLEAR_HOLD = "clear_hold"
ATTR_HOLD_TEMP = "temperature"
ATTR_HOLD_DURATION = "duration"  # uren

# Pump
DEFAULT_PUMP_ANTI_SEIZE_INTERVAL = 24   # hours
DEFAULT_PUMP_ANTI_SEIZE_DURATION = 30   # minutes
DEFAULT_PUMP_POST_HEAT_DELAY = 5        # minutes
DEFAULT_PUMP_MIN_RUN_TIME = 60          # seconds
DEFAULT_PUMP_EXERCISE_TIME = "02:00"    # HH:MM

# ---------------------------------------------------------------------------
# PID
# ---------------------------------------------------------------------------
PID_OUTPUT_MIN = 0.0
PID_OUTPUT_MAX = 100.0

# ---------------------------------------------------------------------------
# Predictive
# ---------------------------------------------------------------------------
PREDICTIVE_HISTORY_SIZE = 30
PREDICTIVE_MIN_SAMPLES = 5

# ---------------------------------------------------------------------------
# Extra state attributes
# ---------------------------------------------------------------------------
ATTR_ALGORITHM = "algorithm"
ATTR_PID_KP = "pid_kp"
ATTR_PID_KI = "pid_ki"
ATTR_PID_KD = "pid_kd"
ATTR_PID_OUTPUT = "pid_output"
ATTR_PID_ERROR = "pid_error"
ATTR_PID_INTEGRAL = "pid_integral"
ATTR_HEATING_RATE = "heating_rate_c_per_min"
ATTR_COOLING_RATE = "cooling_rate_c_per_min"
ATTR_PREDICTED_REACH_TIME = "predicted_reach_time_min"
ATTR_HEATER_ON = "heater_on"
ATTR_COOLER_ON = "cooler_on"
ATTR_WINDOW_OPEN = "window_open"
ATTR_WINDOW_OPEN_SINCE = "window_open_since"
ATTR_PRESENCE = "presence_detected"
ATTR_BOOST_END = "boost_end_time"
ATTR_BOOST_REMAINING = "boost_remaining_min"
ATTR_WEATHER_COMPENSATION = "weather_compensation_active"
ATTR_WEATHER_ADJ = "weather_temp_adjustment"
ATTR_ACTIVE_SCHEDULE = "active_schedule_entry"
ATTR_HEATER_RUNTIME_TODAY = "heater_runtime_today_h"
ATTR_COOLER_RUNTIME_TODAY = "cooler_runtime_today_h"
ATTR_CASCADE_PRIMARY_ON = "cascade_primary_on"
ATTR_CASCADE_SECONDARY_ON = "cascade_secondary_on"
ATTR_CASCADE_SECONDARY_SINCE = "cascade_secondary_since_min"
ATTR_CASCADE_REASON = "cascade_reason"

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
SERVICE_BOOST = "set_boost"
SERVICE_CLEAR_BOOST = "clear_boost"
SERVICE_SET_VACATION = "set_vacation"
SERVICE_CLEAR_VACATION = "clear_vacation"
SERVICE_SET_SCHEDULE = "set_schedule"
SERVICE_CLEAR_SCHEDULE = "clear_schedule"
SERVICE_PUMP_EXERCISE = "trigger_pump_exercise"

# Service attributes
ATTR_BOOST_DURATION = "duration"
ATTR_BOOST_TARGET = "target_temperature"
ATTR_VACATION_START = "start_date"
ATTR_VACATION_END = "end_date"
ATTR_VACATION_TEMP = "temperature"
ATTR_SCHEDULE_ENTRIES = "entries"

# ---------------------------------------------------------------------------
# Schedule entry keys
# ---------------------------------------------------------------------------
SCHED_DAYS = "days"       # list[int] 0=Mon … 6=Sun
SCHED_START = "start"     # "HH:MM"
SCHED_PRESET = "preset"   # one of PRESETS (not PRESET_SCHEDULE/PRESET_BOOST)

# ---------------------------------------------------------------------------
# Sensor / Number / Select unique ID suffixes
# ---------------------------------------------------------------------------
SUFFIX_HEATER_RUNTIME = "_heater_runtime"
SUFFIX_COOLER_RUNTIME = "_cooler_runtime"
SUFFIX_HEATER_ENERGY = "_heater_energy"
SUFFIX_COOLER_ENERGY = "_cooler_energy"
SUFFIX_PID_KP = "_pid_kp"
SUFFIX_PID_KI = "_pid_ki"
SUFFIX_PID_KD = "_pid_kd"
SUFFIX_ALGORITHM = "_algorithm"
SUFFIX_PUMP = "_pump"
# v1.6.0 extra sensoren
SUFFIX_EFFECTIVE_TARGET = "_effective_target"
SUFFIX_TIME_TO_TARGET = "_time_to_target"
SUFFIX_NEXT_SCHEDULE = "_next_schedule"
SUFFIX_HEATING_RATE = "_heating_rate"
SUFFIX_PID_OUTPUT = "_pid_output"
SUFFIX_HOLD_REMAINING = "_hold_remaining"
SUFFIX_PRICE_SETBACK = "_price_setback_active"
