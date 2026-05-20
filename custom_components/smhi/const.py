from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "smhi"
PLATFORMS: list[Platform] = [Platform.WEATHER, Platform.SENSOR, Platform.BINARY_SENSOR]

CONF_NAME = "name"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_USE_HOME_LOCATION = "use_home_location"
CONF_FORECAST_TIMESERIES = "forecast_timeseries"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ENABLE_COMFORT_SENSORS = "enable_comfort_sensors"
CONF_ENABLE_FROST_SENSORS = "enable_frost_sensors"
CONF_ENABLE_SLIPPERY_SENSORS = "enable_slippery_sensors"
CONF_ENABLE_IMPACT_SENSOR = "enable_impact_sensor"
CONF_ENABLE_PRACTICAL_SENSORS = "enable_practical_sensors"
CONF_ENABLE_THERMAL_SENSORS = "enable_thermal_sensors"

DEFAULT_NAME = "SMHI"
DEFAULT_FORECAST_TIMESERIES = 70
DEFAULT_SCAN_INTERVAL_MIN = 30
SETUP_VALIDATION_TIMEOUT = 15

API_BASE = "https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1"

ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_OUT_OF_BOUNDS = "out_of_bounds"
ERROR_INVALID_COORDINATES = "invalid_coordinates"
ERROR_UNKNOWN = "unknown"

ATTR_APPROVED_TIME = "approved_time"
ATTR_CREATED_TIME = "created_time"
ATTR_REFERENCE_TIME = "reference_time"
ATTR_GRID_POINT = "grid_point"
ATTR_INTERVAL_PARAMETERS_START_TIME = "interval_parameters_start_time"
ATTR_STALE = "stale"
ATTR_LAST_SUCCESS = "last_success"
ATTR_LAST_ERROR = "last_error"
ATTR_RAW_CURRENT = "raw_current"
ATTR_RAW_FORECAST = "raw_forecast"

MISSING_VALUE = 9999
PRECIP_FROZEN_NO_PRECIP_VALUE = -9

DAYTIME_START_HOUR = 6
DAYTIME_END_HOUR = 18

PARAMETER_FALLBACK: list[dict] = [
    {"name": "air_temperature", "shortName": "2t", "description": "Air temperature at 2 metres height.", "levelType": "hl", "level": 2, "unit": "Cel", "missingValue": 9999},
    {"name": "wind_from_direction", "shortName": "wd", "description": "Wind from direction at 10 metre.", "levelType": "hl", "level": 10, "unit": "degree", "missingValue": 9999},
    {"name": "wind_speed", "shortName": "ws", "description": "Wind speed at 10 metre.", "levelType": "hl", "level": 10, "unit": "m/s", "missingValue": 9999},
    {"name": "wind_speed_of_gust", "shortName": "i10fg", "description": "Instantaneous 10 metre wind gust", "levelType": "hl", "level": 10, "unit": "m s**-1", "missingValue": 9999},
    {"name": "relative_humidity", "shortName": "2r", "description": "Relative humidity at 2 metres height.", "levelType": "hl", "level": 2, "unit": "percent", "missingValue": 9999},
    {"name": "air_pressure_at_mean_sea_level", "shortName": "pres", "description": "Air pressure at mean sea level.", "levelType": "hmsl", "level": 0, "unit": "hPa", "missingValue": 9999},
    {"name": "visibility_in_air", "shortName": "vis", "description": "Visibility in air.", "levelType": "hl", "level": 2, "unit": "km", "missingValue": 9999},
    {"name": "thunderstorm_probability", "shortName": "tstm", "description": "Thunderstorm probability", "levelType": "hl", "level": 0, "unit": "fraction", "missingValue": 9999},
    {"name": "probability_of_frozen_precipitation", "shortName": "fzpr", "description": "Probability of frozen precipitation.", "levelType": "hl", "level": 0, "unit": "fraction", "missingValue": 9999},
    {"name": "cloud_area_fraction", "shortName": "tcc", "description": "Total Cloud Cover", "levelType": "entireAtmosphere", "level": 2, "unit": "octas", "missingValue": 9999},
    {"name": "low_type_cloud_area_fraction", "shortName": "lcc", "description": "Low cloud cover", "levelType": "entireAtmosphere", "level": 2, "unit": "octas", "missingValue": 9999},
    {"name": "medium_type_cloud_area_fraction", "shortName": "mcc", "description": "Medium cloud cover", "levelType": "entireAtmosphere", "level": 2, "unit": "octas", "missingValue": 9999},
    {"name": "high_type_cloud_area_fraction", "shortName": "hcc", "description": "High cloud cover", "levelType": "entireAtmosphere", "level": 2, "unit": "octas", "missingValue": 9999},
    {"name": "cloud_base_altitude", "shortName": "cdcb", "description": "Cloud base altitude.", "levelType": "entireAtmosphere", "level": 2, "unit": "m", "missingValue": 9999},
    {"name": "cloud_top_altitude", "shortName": "cdct", "description": "Cloud top altitude.", "levelType": "entireAtmosphere", "level": 2, "unit": "m", "missingValue": 9999},
    {"name": "precipitation_amount_mean", "shortName": "tpratemean", "description": "Mean total precipitation amount", "levelType": "hl", "level": 0, "unit": "kg/m2", "missingValue": 9999},
    {"name": "precipitation_amount_min", "shortName": "tpratemin", "description": "Minimum total precipitation amount", "levelType": "hl", "level": 0, "unit": "kg/m2", "missingValue": 9999},
    {"name": "precipitation_amount_max", "shortName": "tpratemax", "description": "Maximum total precipitation amount", "levelType": "hl", "level": 0, "unit": "kg/m2", "missingValue": 9999},
    {"name": "precipitation_amount_median", "shortName": "tpratemedian", "description": "Median total precipitation amount", "levelType": "hl", "level": 0, "unit": "kg/m2", "missingValue": 9999},
    {"name": "precipitation_amount_mean_deterministic", "shortName": "avg_tprate", "description": "Deterministic mean total precipitation amount", "levelType": "hl", "level": 0, "unit": "kg/m2", "missingValue": 9999},
    {"name": "probability_of_precipitation", "shortName": "tp_gt_0p1", "description": "Probability of precipitation of at least 0.1 mm", "levelType": "hl", "level": 0, "unit": "%", "missingValue": 9999},
    {"name": "precipitation_frozen_part", "shortName": "spp", "description": "Frozen part of precipitation.", "levelType": "hl", "level": 0, "unit": "fraction", "missingValue": 9999},
    {"name": "predominant_precipitation_type_at_surface", "shortName": "ptype", "description": "Precipitation type", "levelType": "hl", "level": 0, "unit": "category", "missingValue": 9999},
    {"name": "symbol_code", "shortName": "Wsymb2", "description": "Weather symbol code with 27 different codes.", "levelType": "hl", "level": 0, "unit": "unknown", "missingValue": 9999},
]
