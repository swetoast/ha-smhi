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
- **Swedish climate calibration** - Thresholds optimized for Swedish weather (25°C = hot, not 35°C)
- **Smart binary sensors** - Risk-based triggers (Frost >60%, Slippery >50%)
- **Dynamic language support** - Attributes auto-translate to Swedish
- All sensor groups individually configurable

**Note**: Optional sensors (comfort, frost, slippery, impact, practical, thermal) are calculated values derived from SMHI weather data. They are not official SMHI forecasts.

## Swedish Climate Calibration

All sensors use temperature thresholds adapted for Swedish weather patterns:

- **25°C** = Hot (international: 35°C)
- **30°C** = Extreme heat
- **18°C** = Ideal exercise temperature
- **22°C** = Heat stress begins (international: 25°C)
- **-10°C** = Moderate cold risk (common winter)
- **-25°C** = Extreme cold danger

**Smart Binary Sensors:**
- Frost: Possible triggers at 60% risk
- Slippery: Conditions triggers at 50% risk

*Detailed formula explanations in Advanced Formula Improvements below.*

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
5. Confirm location details (shows grid point and API status)
6. Choose which sensor groups to enable (all enabled by default)
7. Done - integration is ready to use

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

- sensor.smhi_feels_like - Comfort: Feels Like - Apparent temperature combining wind chill and heat index (°C)

### Frost Sensors

- sensor.smhi_frost_risk - Frost: Risk - Frost probability percentage (0-100%)
- binary_sensor.smhi_frost_possible - Frost: Possible - Frost conditions likely (ON/OFF)

### Slippery Sensors

- sensor.smhi_slippery_risk - Slippery: Risk - Ice/snow road danger percentage (0-100%)
- binary_sensor.smhi_slippery_conditions - Slippery: Conditions - Roads likely slippery (ON/OFF)

### Impact Sensor

- sensor.smhi_weather_impact - Impact: Severity - Overall weather severity score (0-100%)

### Practical Sensors

- sensor.smhi_clothing_insulation - Practical: Clothing - Recommended clothing insulation in CLO units
- sensor.smhi_sleep_comfort - Practical: Sleep - Sleep comfort score based on temperature and humidity (%)
- sensor.smhi_exercise_safety - Practical: Exercise - Outdoor exercise safety score (%)

### Thermal Comfort Sensors

- sensor.smhi_thermal_comfort - Thermal: Comfort - Auto-selected thermal comfort index (°C)
- sensor.smhi_humidity_analysis - Thermal: Humidity - Dew point temperature with humidity metrics (°C)
- sensor.smhi_heat_stress_level - Thermal: Heat Stress - Heat stress assessment (0-100%)

## Advanced Formula Improvements

All optional sensors use scientifically-enhanced calculations optimized for Swedish conditions:

### Frost Risk (Sigmoid Curve)
- **Smooth 0-100% transition** instead of binary jumps
- Peak risk at 2°C with gradual decrease
- Considers dew point spread (closer = higher frost risk)
- Enhanced humidity bonuses (>80% RH increases risk)

### Slippery Risk (Peak at 0°C)
- **Most dangerous at 0°C** where ice repeatedly forms/melts
- Weighted scoring: Temperature (50%), Frozen precipitation (30%), Intensity (20%)
- Gradual risk curve from -10°C to +5°C

### Weather Impact (Danger Prioritized)
- **Wind: 40%** - Most dangerous factor (>25 m/s = storm)
- **Precipitation: 30%** - Heavy rain/snow impact
- **Visibility: 20%** - Safety critical (<1km dangerous)
- **Temperature: 10%** - Extreme cold/heat contribution

### Sleep Comfort (Humidity Enhanced)
- **Optimal: 16-19°C + 40-60% RH**
- Detailed humidity penalties (>70% disrupts sleep significantly)
- Weight: 70% temperature, 30% humidity
- High humidity more impactful than in basic formulas

### Exercise Safety (Multi-Factor)
- **Dehydration risk** at high humidity (>85% + 20°C+)
- **Dry air caution** (<20% RH affects breathing)
- **Extreme danger zones**: >35°C or <-30°C
- Categories: Ideal, Safe, Cool, Moderate Risk, Caution, High Risk, Extreme Risk, Extreme Danger

## Language Support

Automatically detects Home Assistant language and translates sensor attributes:

**Translated elements:**
- Exercise categories (Ideal/Idealt, Safe/Säkert, Caution/Varning)
- Risk levels (Danger/Fara, Extreme Caution/Extrem försiktighet)
- Recommendations (Avoid outdoor activity/Undvik utomhusaktivitet)
- Thermal indices (Heat Index/Värmeindex, Summer Comfort/Sommarkomfort)
- Humidity comfort (Oppressive/Kvävande, Comfortable/Bekvämt)

**Enable Swedish:** Settings → System → General → Language → Svenska

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
1. Verify coordinates within SMHI coverage (Sweden and nearby regions)
2. Check internet connectivity
3. Ensure valid coordinates (-90 to 90 latitude, -180 to 180 longitude)

**Stale data warnings**
- `binary_sensor.smhi_api_problem` turns ON during issues
- Check `last_error` attribute for details
- Auto-resumes when API becomes accessible

**Missing sensors**
1. Settings → Devices & Services
2. Find SMHI integration → Configure
3. Enable desired sensor groups → Submit

**Sensors show "null" or "unavailable"**
- Normal behavior - attributes only appear when relevant
- Example: Heat stress shows 0% below 18°C (not applicable)

**Wrong location**
- Reconfigure integration to update coordinates
- SMHI uses nearest grid point (shown during setup)

**Language not switching**
- Settings → System → General → Language
- Applies to sensor attributes only (not UI)
- Restart Home Assistant if needed

## Contributing

Pull requests welcome. For bugs or feature requests, use GitHub issues.

## License

MIT License - see LICENSE file.

## Credits

Weather data: SMHI (Sveriges Meteorologiska och Hydrologiska Institut)

Thermal comfort formulas: Environment Canada (Wind Chill), Steadman (Heat Index), Magnus (Dew Point), Scharlau Seasonal Indices, Thom's Discomfort Index, Summer Simmer Index

## Disclaimer

Not affiliated with SMHI. Weather data provided by SMHI's open data API. For critical decisions, consult official weather warnings.
