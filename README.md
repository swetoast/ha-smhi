# SMHI Weather Integration for Home Assistant

Custom Home Assistant integration for SMHI (Sveriges Meteorologiska och Hydrologiska Institut) weather data. Provides detailed weather forecasts and thermal comfort analysis for Sweden.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Installation

### HACS

1. Add custom repository: `https://github.com/swetoast/ha-smhi`
2. Category: Integration
3. Install "SMHI Weather"
4. Restart Home Assistant

### Manual

1. Download latest release
2. Extract to `config/custom_components/smhi/`
3. Restart Home Assistant

## Setup

Settings → Devices & Services → Add Integration → SMHI

Choose location method:
- Use Home Assistant's configured home location
- Specify custom latitude/longitude coordinates

Configure update interval and forecast steps in integration options.

## Entities

### Weather Entity

**weather.smhi**

Standard Home Assistant weather entity with current conditions and hourly forecasts. Includes temperature, pressure, humidity, wind speed, wind bearing, cloud coverage, visibility, and precipitation data.

### Core Sensors

Always enabled. Cannot be disabled.

**sensor.smhi_precipitation** (mm)

Precipitation amount with ensemble forecasts. Attributes include mean deterministic, ensemble mean/min/max/median, probability of precipitation, frozen precipitation probability and fraction, and precipitation type.

**sensor.smhi_clouds** (octas)

Cloud coverage in octas (0-8 scale). Attributes break down cloud coverage by altitude: low, medium, and high clouds, plus cloud base and top altitudes in meters.

**sensor.smhi_thunderstorm_probability** (%)

Probability of thunderstorms occurring.

**sensor.smhi_symbol_code**

SMHI weather symbol code (1-27). Attributes include text description and corresponding Home Assistant weather condition.

**sensor.smhi_metadata**

API metadata including approved time, created time, reference time, grid point coordinates, and available forecast time steps.

**binary_sensor.smhi_api_problem**

Indicates when API is unavailable or data is stale. ON when there are issues, OFF when operating normally.

### Optional Sensor Groups

All optional groups are enabled by default but can be disabled in integration options.

## Comfort Sensors

**sensor.smhi_feels_like** (°C)

Apparent temperature combining wind chill (cold weather) and heat index (hot weather). Shows what the temperature actually feels like on human skin.

Attributes: wind_chill, heat_index, actual_temperature, dew_point

## Frost Sensors

**sensor.smhi_frost_risk** (%)

Frost probability from 0-100%. Considers current temperature and dew point to calculate likelihood of frost formation.

Attributes: current_temperature, current_dew_point, frost_possible

**binary_sensor.smhi_frost_possible**

ON when conditions favor frost formation. Triggers when temperature is at or below 2°C, or temperature is at or below 4°C with dew point at or below 0°C.

Attributes: temperature, dew_point, humidity

## Slippery Sensors

**sensor.smhi_slippery_risk** (%)

Risk of slippery road conditions from ice or snow. Combines temperature, frozen precipitation fraction, and precipitation amount.

Attributes: current_temperature, conditions_detected

**binary_sensor.smhi_slippery_conditions**

ON when roads are likely slippery. Triggered by temperature between -5°C and 3°C with frozen precipitation, or temperature between -2°C and 1°C with any precipitation.

Attributes: temperature, precipitation_frozen_part, precipitation_amount

## Impact Sensor

**sensor.smhi_weather_impact** (%)

Overall weather severity score from 0-100%. Aggregates multiple factors: temperature extremes, high wind speeds, heavy precipitation, reduced visibility, and thunderstorm probability.

Attributes: current_temperature, current_wind_speed, current_precipitation, current_visibility, current_thunderstorm_probability

## Practical Sensors

**sensor.smhi_clothing_insulation** (CLO)

Recommended clothing insulation in CLO units. Calculates based on temperature and wind speed. Higher values mean more insulation needed.

Attributes: clothing_description ("Winter jacket and layers", "Light jacket", "Shorts and t-shirt", etc.)

**sensor.smhi_sleep_comfort** (%)

Sleep comfort score based on bedroom temperature and humidity. Optimal sleeping temperature is 16-19°C.

Attributes: ideal_range, comfort_level (Excellent, Good, Fair, Poor)

**sensor.smhi_exercise_safety** (%)

Outdoor exercise safety score. Considers feels-like temperature, humidity, and wind. Lower scores indicate more caution needed.

Attributes: safety_category, feels_like_temperature

## Thermal Comfort Sensors

Advanced thermal comfort analysis with multiple indices.

**sensor.smhi_thermal_comfort** (°C)

Primary thermal comfort sensor. Automatically selects the most relevant comfort index based on current temperature:
- Above 27°C: Heat Index
- 17-27°C: Summer comfort metrics
- 10-17°C: Thom's Discomfort Index
- Below 10°C: Seasonal Scharlau or Feels Like

Attributes: actual_temperature, heat_index, humidex, thoms_discomfort, seasonal_scharlau, seasonal_scharlau_perception, current_season, summer_simmer, summer_simmer_perception, relative_strain, relative_strain_perception, thoms_perception, active_index

**sensor.smhi_humidity_analysis** (°C)

Humidity analysis with dew point as the primary value. Dew point is the temperature at which water vapor condenses.

Attributes: dew_point, dew_point_perception, absolute_humidity (g/m³), relative_humidity, temperature, spread (difference between temperature and dew point), frost_point, moist_air_enthalpy (kJ/kg), humidity_comfort

**sensor.smhi_heat_stress_level** (%)

Heat stress assessment from 0-100%. Combines temperature and humidity to calculate physiological heat stress. Above 60% indicates dangerous conditions.

Attributes: risk_level (Safe, Caution, Extreme Caution, Danger, Extreme Danger), recommendation, current_temperature, current_humidity

### Thermal Indices Explained

**Seasonal Scharlau Perception**

Adapts comfort perception based on season and uses appropriate formulas:

Winter (December-February): Valid -5°C to 6°C, uses temperature, humidity, and wind. Perception ranges from "Very Cold" to "Warm".

Spring (March-May): Valid 6°C to 17°C, uses temperature and humidity. Perception ranges from "Too Cold" to "Too Warm".

Summer (June-August): Valid 17°C to 39°C, uses temperature and humidity. Perception ranges from "Cold" to "Hot".

Autumn (September-November): Valid 5°C to 16°C, uses temperature, humidity, and wind. Perception ranges from "Cold" to "Warm".

**Heat Index**

Combines air temperature and relative humidity to determine apparent temperature. Only calculated above 27°C. Based on Steadman's formula.

**Humidex**

Canadian humidity index. Combines temperature and dew point. Higher values indicate greater discomfort from humidity.

**Summer Simmer Index**

Heat stress indicator for warm weather. More sensitive to humidity than heat index.

**Relative Strain Index**

Discomfort assessment for temperatures between 26-35°C. Measures physiological strain from heat.

**Thom's Discomfort Index**

General thermal comfort assessment. Works across a wide temperature range. Originally developed for HVAC applications.

**Dew Point Perception**

Classifies humidity comfort:
- Below 10°C: Dry to Very Dry
- 10-13°C: Pleasant
- 13-16°C: Comfortable
- 16-18°C: Comfortable but humid
- 18-21°C: Somewhat uncomfortable
- 21-24°C: Very humid
- 24-26°C: Extremely uncomfortable
- Above 26°C: Severely high

## Configuration Options

Available in Settings → Integrations → SMHI → Configure:

**Forecast Steps** (1-200, default 70): Number of hourly time steps to fetch from API. More steps = longer forecast period but larger data downloads.

**Update Interval** (5-180 minutes, default 30): How often to poll SMHI API. Shorter intervals = fresher data but more API requests.

**Enable Comfort Sensors** (default ON): Feels-like temperature sensor.

**Enable Frost Sensors** (default ON): Frost risk percentage and binary frost possible sensor.

**Enable Slippery Sensors** (default ON): Slippery risk percentage and binary slippery conditions sensor.

**Enable Impact Sensor** (default ON): Overall weather severity score.

**Enable Practical Sensors** (default ON): Clothing insulation, sleep comfort, and exercise safety sensors.

**Enable Thermal Sensors** (default ON): Thermal comfort index, humidity analysis, and heat stress level sensors.

## Data Sources

All weather data comes from SMHI's open API:
- Endpoint: `https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1`
- Coverage: Sweden and surrounding areas
- Resolution: Grid-based forecasts, coordinates matched to nearest grid point
- Update frequency: SMHI updates forecasts multiple times daily

## Data Quality

**Stale Data Handling**: If API is unavailable, integration continues using last known good data. All sensors include `stale`, `last_success`, and `last_error` attributes for monitoring.

**API Health**: `binary_sensor.smhi_api_problem` shows current API status. When ON, check the `last_error` attribute for details.

## Troubleshooting

**Integration won't add**: Verify coordinates are within SMHI coverage area (Sweden and nearby regions). Check internet connectivity.

**Stale data warnings**: SMHI API is temporarily unavailable. Integration will resume automatically when API is accessible. Existing data remains usable.

**Missing sensors**: Check integration options (Configure button) to enable desired sensor groups.

**Wrong location**: Reconfigure integration to update coordinates. SMHI uses nearest grid point, which may differ slightly from exact coordinates.

## Contributing

Pull requests welcome. For bugs or feature requests, use GitHub issues.

## License

MIT License - see LICENSE file.

## Credits

Weather data: SMHI (Sveriges Meteorologiska och Hydrologiska Institut)

Thermal comfort formulas: Environment Canada (Wind Chill), Steadman (Heat Index), Magnus (Dew Point), Scharlau Seasonal Indices, Thom's Discomfort Index, Summer Simmer Index

## Disclaimer

Not affiliated with SMHI. Weather data provided by SMHI's open data API. For critical decisions, consult official weather warnings.

