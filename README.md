# SMHI Weather Integration for Home Assistant

Custom Home Assistant integration for SMHI (Sveriges Meteorologiska och Hydrologiska Institut) weather data. Provides detailed weather forecasts and thermal comfort analysis for Sweden.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- Weather entity with current conditions and hourly forecasts
- Precipitation tracking with ensemble predictions
- Cloud coverage analysis by altitude
- Thunderstorm probability monitoring
- Thermal comfort indices with seasonal adaptation
- Frost and ice risk assessment
- Practical sensors for clothing, sleep, and exercise
- All sensor groups can be individually enabled/disabled
- Multi-language support (English, Swedish)

## Installation

### HACS

1. Go to HACS → Integrations
2. Click the three dots menu → Custom repositories
3. Add: `https://github.com/swetoast/ha-smhi`
4. Category: Integration
5. Search for "SMHI Weather"
6. Click Install
7. Restart Home Assistant
8. Go to Settings → Devices & Services → Add Integration
9. Search for "SMHI" and configure

### Manual

1. Download the latest release
2. Copy the `custom_components/smhi` folder to your `config/custom_components/` directory
3. Restart Home Assistant
4. Go to Settings → Devices & Services → Add Integration
5. Search for "SMHI" and configure

## Configuration

### Setup

1. Go to Settings → Devices & Services
2. Click Add Integration
3. Search for "SMHI"
4. Choose location method:
   - Use Home Assistant's home location, or
   - Specify custom latitude/longitude coordinates
5. Configure update interval and forecast steps

### Options

After setup, click Configure on the SMHI integration:

- **Forecast Steps** (1-200, default 70): Number of hourly forecast steps
- **Update Interval** (5-180 minutes, default 30): How often to fetch data
- **Enable Comfort Sensors** (default ON): Feels-like temperature
- **Enable Frost Sensors** (default ON): Frost risk % and binary sensor
- **Enable Slippery Sensors** (default ON): Ice/snow road risk % and binary sensor
- **Enable Impact Sensor** (default ON): Weather severity score
- **Enable Practical Sensors** (default ON): Clothing, sleep, exercise
- **Enable Thermal Sensors** (default ON): Advanced thermal comfort indices

## Entities

### Weather Entity

- weather.smhi - Current conditions with hourly forecasts (temperature, pressure, humidity, wind, cloud coverage, precipitation, visibility)

### Core Sensors (Always Active)

- sensor.smhi_precipitation - Precipitation amount in mm with ensemble forecasts (mean, min, max, median)
- sensor.smhi_clouds - Cloud coverage in octas (0-8) with altitude breakdown (low, medium, high)
- sensor.smhi_thunderstorm_probability - Probability of thunderstorms (%)
- sensor.smhi_symbol_code - SMHI weather symbol code (1-27)
- sensor.smhi_metadata - API metadata and grid point information
- binary_sensor.smhi_api_problem - API health status (ON when issues detected)

### Comfort Sensors

- sensor.smhi_feels_like - Apparent temperature combining wind chill and heat index (°C)

### Frost Sensors

- sensor.smhi_frost_risk - Frost probability percentage (0-100%)
- binary_sensor.smhi_frost_possible - Frost conditions likely (ON/OFF)

### Slippery Sensors

- sensor.smhi_slippery_risk - Ice/snow road danger percentage (0-100%)
- binary_sensor.smhi_slippery_conditions - Roads likely slippery (ON/OFF)

### Impact Sensor

- sensor.smhi_weather_impact - Overall weather severity score (0-100%)

### Practical Sensors

- sensor.smhi_clothing_insulation - Recommended clothing insulation in CLO units
- sensor.smhi_sleep_comfort - Sleep comfort score based on temperature and humidity (%)
- sensor.smhi_exercise_safety - Outdoor exercise safety score (%)

### Thermal Comfort Sensors

- sensor.smhi_thermal_comfort - Auto-selected thermal comfort index (°C)
- sensor.smhi_humidity_analysis - Dew point temperature with humidity metrics (°C)
- sensor.smhi_heat_stress_level - Heat stress assessment (0-100%)

## Thermal Comfort Details

### Seasonal Scharlau Perception

Automatically adapts comfort perception based on season:

**Winter (December-February)**: -5°C to 6°C, uses temperature, humidity, and wind
- Perception: Very Cold → Cold → Cool → Slightly Cool → Comfortable → Warm

**Spring (March-May)**: 6°C to 17°C, uses temperature and humidity
- Perception: Too Cold → Cool → Slightly Cool → Comfortable → Slightly Warm → Too Warm

**Summer (June-August)**: 17°C to 39°C, uses temperature and humidity
- Perception: Cold → Cool → Slightly Cool → Comfortable → Slightly Warm → Warm → Hot

**Autumn (September-November)**: 5°C to 16°C, uses temperature, humidity, and wind
- Perception: Cold → Cool → Comfortable → Mild → Warm

### Other Thermal Indices

- **Heat Index**: Combines temperature and humidity (Steadman formula)
- **Humidex**: Canadian humidity index using dew point
- **Summer Simmer**: Heat stress indicator for warm weather
- **Relative Strain**: Discomfort for 26-35°C range
- **Thom's Discomfort**: General thermal comfort assessment

### Humidity Comfort

Dew point perception categories:
- Below 10°C: Dry to Very Dry
- 10-13°C: Pleasant
- 13-16°C: Comfortable
- 16-18°C: Comfortable but humid
- 18-21°C: Somewhat uncomfortable
- 21-24°C: Very humid
- 24-26°C: Extremely uncomfortable
- Above 26°C: Severely high

## Data Source

All weather data from SMHI's open API:
- Endpoint: `https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1`
- Coverage: Sweden and surrounding areas
- Resolution: Grid-based forecasts
- Updates: Multiple times daily

## Troubleshooting

**Integration won't add**
- Verify coordinates are within SMHI coverage area (Sweden and nearby regions)
- Check internet connectivity

**Stale data warnings**
- `binary_sensor.smhi_api_problem` will be ON
- Check `last_error` attribute for details
- SMHI API may be temporarily unavailable
- Integration will resume automatically when API is accessible

**Missing sensors**
- Check integration options (Configure button)
- Enable desired sensor groups

**Wrong location**
- Reconfigure integration to update coordinates
- SMHI uses nearest grid point, which may differ slightly from exact coordinates

## Contributing

Pull requests welcome. For bugs or feature requests, use GitHub issues.

## License

MIT License - see LICENSE file.

## Credits

Weather data: SMHI (Sveriges Meteorologiska och Hydrologiska Institut)

Thermal comfort formulas: Environment Canada (Wind Chill), Steadman (Heat Index), Magnus (Dew Point), Scharlau Seasonal Indices, Thom's Discomfort Index, Summer Simmer Index

## Disclaimer

Not affiliated with SMHI. Weather data provided by SMHI's open data API. For critical decisions, consult official weather warnings.

