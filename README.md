# SMHI Weather Integration for Home Assistant

Custom Home Assistant integration for SMHI (Sveriges Meteorologiska och Hydrologiska Institut) weather data. Provides detailed weather forecasts and thermal comfort analysis for Sweden.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- Weather entity with current conditions and hourly/daily/twice-daily forecasts
- Precipitation tracking with ensemble predictions
- Cloud coverage analysis by altitude
- Thunderstorm probability monitoring with risk levels
- Thermal comfort indices with seasonal adaptation
- Frost and ice risk assessment with intelligent binary sensors
- Practical sensors for clothing, sleep, and exercise
- 4 detailed safety sensors (black ice, fog, frozen precipitation, weather changes)
- **Advanced clothing sensor** with layered breakdown and forecast awareness
- **Smart binary sensors** with hysteresis and time-of-day awareness
- All sensor groups individually configurable

**Note**: Optional sensors (comfort, frost, slippery, impact, practical, thermal, detailed) are calculated values derived from SMHI weather data. They are not official SMHI forecasts.

## Swedish Climate Calibration

All sensors use temperature thresholds adapted for Swedish weather patterns:

- **22°C** = Heat stress begins, heat index activates (international: 27°C)
- **25°C** = Hot (international: 35°C)
- **30°C** = Extreme heat
- **18°C** = Ideal exercise temperature
- **-10°C** = Moderate cold risk (common winter)
- **-25°C** = Extreme cold danger

**Smart Binary Sensors (with Hysteresis):**
- Frost: Night threshold 55% (more sensitive), day threshold 65% (less sensitive), turns off at 45%/55%
- Slippery: Triggers at 50%, turns off at 40% (prevents rapid on/off cycling)

*Hysteresis prevents flapping. Time-of-day awareness for frost matches real-world patterns (coldest at dawn).*

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
6. Choose which sensor groups to enable (all enabled by default except detailed sensors)
7. Done - integration is ready to use

### Options

After setup, click Configure on the SMHI integration:

- **Forecast Steps** (1-200, default 70): Number of hourly forecast steps
- **Update Interval** (5-180 minutes, default 30): How often to fetch data
- **Enable Comfort Sensors** (default ON): Feels-like temperature
- **Enable Frost Sensors** (default ON): Frost risk % and binary sensor
- **Enable Slippery Sensors** (default ON): Ice/snow road risk % and binary sensor
- **Enable Impact Sensor** (default ON): Weather severity score
- **Enable Practical Sensors** (default ON): Clothing, sleep, exercise recommendations
- **Enable Thermal Sensors** (default ON): Advanced thermal comfort indices
- **Enable Detailed Sensors** (default OFF): 4 safety sensors (black ice, fog, frozen precipitation, weather changes)

## Entities

### Weather Entity

- weather.smhi - Current conditions with hourly/daily/twice-daily forecasts

### Core Sensors (Always Active)

- sensor.smhi_precipitation - Precipitation amount (mm) with ensemble predictions (mean, min, max, median)
- sensor.smhi_clouds - Cloud coverage (octas) with altitude breakdown (low, medium, high)
- sensor.smhi_thunderstorm_probability - Thunderstorm probability (%) with risk level attribute
- sensor.smhi_symbol_code - SMHI weather symbol code (1-27)
- sensor.smhi_metadata - API metadata and diagnostics
- binary_sensor.smhi_api_problem - API health status

### Comfort Sensors (Optional, Default ON)

- sensor.smhi_feels_like - Apparent temperature (°C)

### Frost Sensors (Optional, Default ON)

- sensor.smhi_frost_risk - Frost probability with smooth sigmoid curve (0-100%)
- binary_sensor.smhi_frost_possible - Frost likely (triggers at 60% risk)

### Slippery Sensors (Optional, Default ON)

- sensor.smhi_slippery_risk - Ice/snow road danger (0-100%)
- binary_sensor.smhi_slippery_conditions - Slippery roads likely (triggers at 50% risk)

### Impact Sensor (Optional, Default ON)

- sensor.smhi_weather_impact - Overall weather severity (0-100%)

### Practical Sensors (Optional, Default ON)

- sensor.smhi_practical_clothing - Weather-aware clothing recommendations (CLO units) with layered breakdown
  - **Attributes:** base_layer, mid_layer, outer_layer, bottoms, footwear, accessories
  - **Rain protection:** rain_note, waterproof_layer, umbrella recommendation
  - **Wind protection:** wind_note with Swedish layering philosophy (windproof > thick layers)
  - **Forecast awareness:** carry_extra_layer, later_note (checks 6 hours ahead for temperature drops/rain)
  - **Context:** effective_temperature, sun_adjustment, activity_mode (auto-detected from time)
  - **Transparency:** decision_factors list, confidence level
- sensor.smhi_practical_sleep - Sleep comfort score (%)
- sensor.smhi_practical_exercise - Outdoor exercise safety (%)
- sensor.smhi_practical_exercise_perception - Exercise safety category (enum)

### Thermal Sensors (Optional, Default ON)

- sensor.smhi_thermal_comfort - Auto-selected comfort index (°C)
- sensor.smhi_thermal_comfort_perception - Seasonal comfort category (enum)
- sensor.smhi_humidity_analysis - Dew point with humidity metrics (°C)
- sensor.smhi_humidity_perception - Humidity comfort category (enum)
- sensor.smhi_heat_stress_level - Heat stress assessment (0-100%)
- sensor.smhi_heat_stress_perception - Heat stress category (enum)

### Detailed Safety Sensors (Optional, Default OFF)

- sensor.smhi_frozen_precipitation_probability - Snow/ice probability (%) with expectation levels
- sensor.smhi_safety_black_ice_risk - Black ice danger assessment (none/low/moderate/high/very_high)
- sensor.smhi_safety_fog_probability - Fog likelihood based on dew point spread (0-100%)
- sensor.smhi_safety_weather_change_alert - Rapid weather change detection (stable/minor/moderate/significant/severe)

## Advanced Formula Improvements

All optional sensors use enhanced calculations optimized for Swedish climate:

### Frost Risk (Sigmoid Curve)
- **Smooth 0-100% transition** instead of binary jumps
- Peak risk at 2°C with gradual decrease
- Considers dew point spread (closer = higher frost risk)
- Enhanced humidity bonuses (>80% RH increases risk)

**Binary Sensor (with Hysteresis & Time Awareness):**
- Night (22:00-08:00): Triggers at 55%, turns off at 45% (frost peaks at dawn)
- Day (08:00-22:00): Triggers at 65%, turns off at 55% (sun reduces risk)
- Hysteresis prevents rapid on/off cycling when hovering near threshold

### Slippery Risk (Peak at 0°C)
- **Most dangerous at 0°C** where ice repeatedly forms/melts
- Weighted scoring: Temperature (50%), Frozen precipitation (30%), Intensity (20%)
- Gradual risk curve from -10°C to +5°C

**Binary Sensor (with Hysteresis & Special Cases):**
- Normal: Triggers at 50%, turns off at 40%
- Heavy snow/ice (>2mm + 50% frozen): Triggers at 40%, turns off at 35% (very dangerous)
- Hysteresis prevents flapping

### Weather Impact (Danger Prioritized)
- **Wind: 40%** - Most dangerous factor (>25 m/s = storm)
- **Precipitation: 30%** - Heavy rain/snow impact
- **Visibility: 20%** - Safety critical (<1km dangerous)
- **Temperature: 10%** - Extreme cold/heat contribution

### Sleep Comfort (Humidity Enhanced)
- **Optimal: 16-19°C + 40-60% RH**
- Detailed humidity penalties (>70% disrupts sleep significantly)
- Weight: 70% temperature, 30% humidity

### Exercise Safety (Multi-Factor)
- **Dehydration risk** at high humidity (>85% + 20°C+)
- **Dry air caution** (<20% RH affects breathing)
- **Extreme danger zones**: >35°C or <-30°C
- Categories: Ideal, Safe, Cool, Moderate Risk, Caution, High Risk, Extreme Risk, Extreme Danger

### Practical Clothing (Weather-Aware & Layered)
**Structured layered recommendations** with forecast awareness:
- **Layers:** Split into base_layer, mid_layer, outer_layer, bottoms, footwear, accessories
- **Activity mode:** Auto-detected from time (commuting 07-09/16-19, walking 10-15, general other times)
- **Forecast checking:** Scans 6 hours ahead for temperature drops (>5°C) or rain starting
- **Context factors:**
  • Temperature and wind (JAG/TI wind chill)
  • Cloud cover (sunny +1.5°C, cloudy -0.5°C)
  • Humidity (high humidity feels cooler)
  • Precipitation (rain/snow requires waterproof layer)
  • Forecast trend (dress for where weather is going)
  • Wind gusts (prioritize windproof over thick layers)

**Swedish layering philosophy:** Windproof shell > thick layers for wind protection. Each CLO band precisely matched to engineering garment values.

**CLO accuracy:** All bands corrected to match ASHRAE engineering table (boots 0.10, sweater types distinguished, winter base layer 0.40 CLO).

Example: 15°C + sunny + calm → Base: "Long sleeve shirt", Mid: "Light overshirt if cooler", Outer: "None", with sun_adjustment: -1.5°C shown

### Heat Index
**Activates at 22°C** (not 27°C like standard NWS formula):
- Simplified humidity discomfort formula for mild heat (22-27°C)
- Full Steadman formula for extreme heat (27°C+)
- Reflects Swedish heat sensitivity - 25°C + 75% humidity feels uncomfortable

### Detailed Safety Sensors
- **Black Ice Risk**: Combines temperature (-4°C to +2°C danger zone), precipitation, humidity, dew point spread
- **Fog Probability**: Based on temperature-dew point spread (<2°C = high risk) + humidity
- **Frozen Precipitation**: Probability with expectation levels (very unlikely to very likely)
- **Weather Change Alert**: Compares current vs 1hr/3hr forecast for rapid changes in temp, pressure, wind, precipitation

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

## Clothing Sensor Attributes

The `sensor.smhi_practical_clothing` provides rich structured data for easy dashboard rendering:

**Layered Clothing:**
```yaml
clothing_level: Mild spring/autumn
base_layer: Long sleeve shirt
mid_layer: Light overshirt if cooler
outer_layer: None
bottoms: Trousers
footwear: Normal shoes
accessories: [Sunglasses]
```

**Protection:**
```yaml
rain_protection: none / light_shell / waterproof / bring_backup
rain_note: No rain expected
waterproof_layer: false
umbrella: false

wind_protection: none / light_windproof / windproof / windproof_required
wind_note: Calm conditions - focus on insulation
```

**Forecast Awareness:**
```yaml
carry_extra_layer: false
later_note: null  # or "Temperature drops to 8°C after 22:00 - bring extra layer"
```

**Context:**
```yaml
effective_temperature: 15.1  # What it actually feels like
sun_adjustment: -1.5  # Sunny makes it feel warmer
activity_mode: commuting  # or walking, general
activity_note: Light layers suitable for active commuting
```

**Transparency:**
```yaml
decision_factors:
  - 14.9°C mild temperature
  - Calm wind
  - Sunny, clear sky
confidence: high
```

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
4. Restart Home Assistant

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
