from __future__ import annotations

from enum import StrEnum
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfTemperature
try:
    from homeassistant.const import UnitOfPrecipitationDepth
except ImportError:
    class UnitOfPrecipitationDepth:  # type: ignore[no-redef]
        MILLIMETERS = "mm"
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_APPROVED_TIME,
    ATTR_CREATED_TIME,
    ATTR_GRID_POINT,
    ATTR_LAST_ERROR,
    ATTR_LAST_SUCCESS,
    ATTR_REFERENCE_TIME,
    ATTR_STALE,
    CONF_ENABLE_COMFORT_SENSORS,
    CONF_ENABLE_DETAILED_SENSORS,
    CONF_ENABLE_FROST_SENSORS,
    CONF_ENABLE_IMPACT_SENSOR,
    CONF_ENABLE_PRACTICAL_SENSORS,
    CONF_ENABLE_SLIPPERY_SENSORS,
    CONF_ENABLE_THERMAL_SENSORS,
    CONF_NAME,
    DOMAIN,
)
from .helpers import clean_value, condition_from_symbol, current_data_from_payload, octas_to_percent, ptype_description, symbol_description


# Translation dictionaries for sensor attributes
TRANSLATIONS = {
    "en": {
        # Exercise categories
        "ideal": "Ideal",
        "safe": "Safe",
        "cool": "Cool",
        "moderate_risk": "Moderate Risk",
        "caution_hot": "Caution - Hot",
        "caution_cold": "Caution - Cold",
        "high_risk": "High Risk",
        "extreme_risk": "Extreme Risk",
        "extreme_danger": "Extreme Danger",
        "high_dehydration_risk": "High Dehydration Risk",
        "extreme_dehydration_risk": "Extreme Dehydration Risk",
        "caution_hydration": "Caution - Hydration",
        "monitor_hydration": "Monitor Hydration",
        "dry_air_caution": "Dry Air Caution",
        # Risk levels
        "caution": "Caution",
        "extreme_caution": "Extreme Caution",
        "danger": "Danger",
        # Recommendations
        "normal_activity_safe": "Normal activity safe",
        "take_breaks_drink_water": "Take breaks, drink water",
        "limit_outdoor_activity": "Limit outdoor activity, stay hydrated",
        "avoid_outdoor_activity": "Avoid outdoor activity",
        # Thermal indices
        "heat_index": "Heat Index",
        "summer_comfort": "Summer Comfort",
        "thoms_discomfort": "Thoms Discomfort",
        "actual_temperature": "Actual Temperature",
        # Humidity levels
        "oppressive": "Oppressive",
        "very_humid": "Very Humid",
        "humid": "Humid",
        "comfortable": "Comfortable",
        "pleasant": "Pleasant",
        "dry": "Dry",
        "very_dry": "Very Dry",
        "comfortable_but_humid": "Comfortable but humid",
        "somewhat_uncomfortable": "Somewhat uncomfortable",
        "extremely_uncomfortable": "Extremely uncomfortable",
        "severely_high": "Severely high",
    },
    "sv": {
        # Exercise categories
        "ideal": "Idealt",
        "safe": "Säkert",
        "cool": "Svalt",
        "moderate_risk": "Måttlig risk",
        "caution_hot": "Varning - Varmt",
        "caution_cold": "Varning - Kallt",
        "high_risk": "Hög risk",
        "extreme_risk": "Extrem risk",
        "extreme_danger": "Extrem fara",
        "high_dehydration_risk": "Hög dehydreringsrisk",
        "extreme_dehydration_risk": "Extrem dehydreringsrisk",
        "caution_hydration": "Varning - Vätskebalans",
        "monitor_hydration": "Övervaka vätskebalans",
        "dry_air_caution": "Varning - Torr luft",
        # Risk levels
        "caution": "Varning",
        "extreme_caution": "Extrem försiktighet",
        "danger": "Fara",
        # Recommendations
        "normal_activity_safe": "Normal aktivitet säker",
        "take_breaks_drink_water": "Ta pauser, drick vatten",
        "limit_outdoor_activity": "Begränsa utomhusaktivitet, håll dig hydrerad",
        "avoid_outdoor_activity": "Undvik utomhusaktivitet",
        # Thermal indices
        "heat_index": "Värmeindex",
        "summer_comfort": "Sommarkomfort",
        "thoms_discomfort": "Thoms obehag",
        "actual_temperature": "Verklig temperatur",
        # Humidity levels
        "oppressive": "Kvävande",
        "very_humid": "Mycket fuktigt",
        "humid": "Fuktigt",
        "comfortable": "Bekvämt",
        "pleasant": "Behagligt",
        "dry": "Torrt",
        "very_dry": "Mycket torrt",
        "comfortable_but_humid": "Bekvämt men fuktigt",
        "somewhat_uncomfortable": "Något obekvämt",
        "extremely_uncomfortable": "Extremt obekvämt",
        "severely_high": "Extremt hög",
    }
}


def _translate(key: str, hass: HomeAssistant) -> str:
    """Get translated text based on Home Assistant language."""
    language = hass.config.language
    # Default to Swedish if language is sv, otherwise English
    lang = "sv" if language == "sv" else "en"
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)


# Perception Enum Classes for ENUM sensors
class ExerciseSafetyCategory(StrEnum):
    """Exercise safety perception categories."""
    IDEAL = "ideal"
    SAFE = "safe"
    COOL = "cool"
    MODERATE_RISK = "moderate_risk"
    CAUTION_HOT = "caution_hot"
    CAUTION_COLD = "caution_cold"
    HIGH_RISK = "high_risk"
    EXTREME_RISK = "extreme_risk"
    EXTREME_DANGER = "extreme_danger"
    HIGH_DEHYDRATION_RISK = "high_dehydration_risk"
    EXTREME_DEHYDRATION_RISK = "extreme_dehydration_risk"
    CAUTION_HYDRATION = "caution_hydration"
    MONITOR_HYDRATION = "monitor_hydration"
    DRY_AIR_CAUTION = "dry_air_caution"


class RiskLevel(StrEnum):
    """Risk level categories."""
    SAFE = "safe"
    CAUTION = "caution"
    EXTREME_CAUTION = "extreme_caution"
    DANGER = "danger"
    EXTREME_DANGER = "extreme_danger"


class HumidityComfort(StrEnum):
    """Humidity comfort perception."""
    OPPRESSIVE = "oppressive"
    VERY_HUMID = "very_humid"
    HUMID = "humid"
    COMFORTABLE = "comfortable"
    PLEASANT = "pleasant"
    DRY = "dry"
    VERY_DRY = "very_dry"


class ThermalIndex(StrEnum):
    """Active thermal comfort index names."""
    HEAT_INDEX = "heat_index"
    SUMMER_COMFORT = "summer_comfort"
    THOMS_DISCOMFORT = "thoms_discomfort"
    ACTUAL_TEMPERATURE = "actual_temperature"


def _payload(coordinator) -> dict[str, Any]:
    return coordinator.current_payload()


def _data(coordinator) -> dict[str, Any]:
    return current_data_from_payload(_payload(coordinator))


def calculate_dew_point(temp_c: float, humidity: float) -> float:
    """Calculate dew point using Sonntag formula (more accurate than Magnus).
    
    Source: http://wahiduddin.net/calc/density_algorithms.htm
    """
    import math
    
    # Sonntag formula for saturation vapor pressure
    A0 = 373.15 / (273.15 + temp_c)
    SUM = -7.90298 * (A0 - 1)
    SUM += 5.02808 * math.log(A0, 10)
    SUM += -1.3816e-7 * (pow(10, (11.344 * (1 - 1 / A0))) - 1)
    SUM += 8.1328e-3 * (pow(10, (-3.49149 * (A0 - 1))) - 1)
    SUM += math.log(1013.246, 10)
    
    # Vapor pressure
    VP = pow(10, SUM - 3) * humidity
    
    # Dew point temperature
    Td = math.log(VP / 0.61078)
    Td = (241.88 * Td) / (17.558 - Td)
    
    return Td


def calculate_wind_chill(temp_c: float, wind_kmh: float) -> float | None:
    """Calculate wind chill (Environment Canada formula)."""
    if temp_c > 10 or wind_kmh < 4.8:
        return None
    return 13.12 + 0.6215 * temp_c - 11.37 * (wind_kmh ** 0.16) + 0.3965 * temp_c * (wind_kmh ** 0.16)


def calculate_heat_index(temp_c: float, humidity: float) -> float | None:
    """Calculate heat index adapted for Swedish climate sensitivity.
    
    Swedes are not acclimatized to heat - 22°C with humidity feels warm.
    Uses simplified formula for mild heat (22-27°C) and full NWS formula for extreme heat (27°C+).
    
    Source: Adapted from http://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml
    """
    # Swedish adaptation: start at 22°C instead of 27°C
    if temp_c < 22:
        return None
    
    import math
    
    # For mild Swedish heat (22-27°C): simple humidity discomfort formula
    if temp_c < 27:
        # Simplified heat index for moderate temperatures
        # Base: temperature feels like itself
        # Add humidity penalty: high humidity makes it feel warmer
        humidity_factor = (humidity - 40) / 10  # 0 at 40%, +6 at 100%
        
        if humidity > 60:
            # Noticeable humidity effect
            heat_index = temp_c + (humidity_factor * 0.5)
        elif humidity > 50:
            # Slight humidity effect  
            heat_index = temp_c + (humidity_factor * 0.3)
        else:
            # Dry heat - minimal effect
            heat_index = temp_c + (humidity_factor * 0.1)
        
        return heat_index
    
    # For extreme heat (27°C+): use full NWS formula
    # Convert to Fahrenheit for calculation
    fahrenheit = temp_c * 9/5 + 32
    
    # Simple formula as initial estimate
    hi = 0.5 * (fahrenheit + 61.0 + ((fahrenheit - 68.0) * 1.2) + (humidity * 0.094))
    
    # Use full regression equation if simple formula > 79°F
    if hi > 79:
        hi = -42.379 + 2.04901523 * fahrenheit
        hi += 10.14333127 * humidity
        hi += -0.22475541 * fahrenheit * humidity
        hi += -0.00683783 * pow(fahrenheit, 2)
        hi += -0.05481717 * pow(humidity, 2)
        hi += 0.00122874 * pow(fahrenheit, 2) * humidity
        hi += 0.00085282 * fahrenheit * pow(humidity, 2)
        hi += -0.00000199 * pow(fahrenheit, 2) * pow(humidity, 2)
    
    # Adjustments for low humidity
    if humidity < 13 and fahrenheit >= 80 and fahrenheit <= 112:
        hi -= ((13 - humidity) * 0.25) * math.sqrt((17 - abs(fahrenheit - 95)) * 0.05882)
    
    # Adjustments for high humidity
    elif humidity > 85 and fahrenheit >= 80 and fahrenheit <= 87:
        hi += ((humidity - 85) * 0.1) * ((87 - fahrenheit) * 0.2)
    
    # Convert back to Celsius
    return (hi - 32) * 5/9


def calculate_feels_like(temp_c: float, wind_ms: float, humidity: float) -> float:
    """Calculate feels-like temperature combining wind chill and heat index."""
    wind_kmh = wind_ms * 3.6
    wind_chill = calculate_wind_chill(temp_c, wind_kmh)
    if wind_chill is not None:
        return wind_chill
    heat_index = calculate_heat_index(temp_c, humidity)
    if heat_index is not None:
        return heat_index
    return temp_c


def calculate_frost_risk(temp_c: float, humidity: float, dew_point: float) -> int:
    """Calculate frost risk (0-100%) with sigmoid curve for smooth transitions."""
    import math
    
    # No risk above 5°C
    if temp_c > 5:
        return 0
    
    # Base risk from temperature using sigmoid curve
    # Center at 2°C, steep transition around freezing
    temp_risk = 100 / (1 + math.exp((temp_c - 2) * 1.5))
    
    # Dew point spread factor (temp - dew_point)
    # Smaller spread = higher condensation risk
    spread = temp_c - dew_point
    
    if spread < 1:
        # Very close to dew point = high condensation risk
        spread_multiplier = 1.3
    elif spread < 2:
        spread_multiplier = 1.15
    elif spread < 3:
        spread_multiplier = 1.05
    else:
        spread_multiplier = 1.0
    
    # Humidity bonus (higher humidity = more moisture for frost)
    if humidity > 80:
        humidity_bonus = 15
    elif humidity > 70:
        humidity_bonus = 10
    elif humidity > 60:
        humidity_bonus = 5
    else:
        humidity_bonus = 0
    
    # Calculate final risk
    risk = (temp_risk * spread_multiplier) + humidity_bonus
    
    return min(100, max(0, int(risk)))


def calculate_slippery_risk(temp_c: float, precip_frozen: float | None, precip_amount: float | None) -> int:
    """Calculate slippery conditions risk (0-100%) with peak danger at 0°C."""
    # No risk outside dangerous temperature range
    if temp_c < -10 or temp_c > 5:
        return 0
    
    # Base risk from distance to 0°C (most dangerous point)
    # Peak danger at 0°C where ice forms/melts repeatedly
    distance_from_zero = abs(temp_c)
    
    if distance_from_zero <= 1:
        # Within 1°C of freezing = very high base risk
        temp_risk = 50
    elif distance_from_zero <= 2:
        temp_risk = 40
    elif distance_from_zero <= 3:
        temp_risk = 30
    elif distance_from_zero <= 5:
        temp_risk = 20
    else:
        temp_risk = 10
    
    # Frozen precipitation factor (30% weight)
    frozen_risk = 0
    if precip_frozen is not None:
        if precip_frozen > 0.7:
            frozen_risk = 30
        elif precip_frozen > 0.5:
            frozen_risk = 25
        elif precip_frozen > 0.3:
            frozen_risk = 20
        elif precip_frozen > 0.1:
            frozen_risk = 10
    
    # Precipitation intensity factor (20% weight)
    precip_risk = 0
    if precip_amount is not None:
        if precip_amount > 2:
            precip_risk = 20
        elif precip_amount > 1:
            precip_risk = 15
        elif precip_amount > 0.5:
            precip_risk = 10
        elif precip_amount > 0.1:
            precip_risk = 5
    
    total_risk = temp_risk + frozen_risk + precip_risk
    return min(100, max(0, int(total_risk)))


def calculate_weather_impact(temp_c: float, wind_ms: float, precip: float | None, 
                            visibility: float | None, thunder_prob: float | None) -> int:
    """Calculate overall weather impact score (0-100) with danger-prioritized weighting."""
    impact = 0
    
    # High wind (40% weight) - most dangerous factor
    wind_kmh = wind_ms * 3.6
    if wind_kmh > 25:  # Storm force (>25 m/s = 90 km/h)
        impact += 40
    elif wind_kmh > 20:  # Very strong
        impact += 32
    elif wind_kmh > 15:  # Strong
        impact += 24
    elif wind_kmh > 10:  # Fresh
        impact += 12
    
    # Heavy precipitation (30% weight)
    if precip is not None:
        if precip > 10:  # Very heavy
            impact += 30
        elif precip > 5:  # Heavy
            impact += 22
        elif precip > 2:  # Moderate
            impact += 15
        elif precip > 0.5:  # Light
            impact += 8
    
    # Low visibility (20% weight) - safety critical
    if visibility is not None:
        if visibility < 0.5:  # Very poor
            impact += 20
        elif visibility < 1:  # Poor
            impact += 16
        elif visibility < 5:  # Moderate
            impact += 10
        elif visibility < 10:  # Reduced
            impact += 5
    
    # Temperature extremes (10% weight) - adjusted for Swedish climate
    if temp_c < -25:  # Extreme cold (dangerous in Sweden)
        impact += 10
    elif temp_c < -15:  # Very cold (common in northern Sweden)
        impact += 7
    elif temp_c < -10:  # Cold (normal winter)
        impact += 4
    elif temp_c > 30:  # Extreme heat for Sweden
        impact += 10
    elif temp_c > 27:  # Very hot for Sweden
        impact += 7
    elif temp_c > 25:  # Hot for Swedish standards
        impact += 4
    
    # Thunderstorm bonus (adds to total, not weighted)
    if thunder_prob is not None:
        if thunder_prob > 0.7:
            impact += 15
        elif thunder_prob > 0.5:
            impact += 10
        elif thunder_prob > 0.3:
            impact += 5
    
    return min(100, max(0, int(impact)))


def calculate_clo_value(temp_c: float, wind_ms: float, coordinator=None) -> float:
    """Calculate clothing insulation for Swedish outdoor conditions.
    
    Enhanced version that considers:
    - Temperature and wind chill
    - Precipitation (rain/snow requires protection)
    - Cloud cover (sunny feels warmer than cloudy)
    - Humidity (affects perceived temperature)
    - Forecast trends (dress for where it's going, not just now)
    - Swedish acclimatization and outdoor norms
    
    Target: Comfortable for 15-30 min outdoor exposure with light activity.
    """
    wind_ms = max(float(wind_ms or 0), 0.0)
    
    # Get weather context if coordinator available
    precip_mm = 0.0
    cloud_octas = 4  # default: partly cloudy
    humidity_pct = 70  # default
    temp_trend = 0.0  # temperature change in next 2 hours
    precip_prob = 0.0
    
    if coordinator:
        try:
            data = coordinator.current_payload()
            if data and "timeSeries" in data and len(data["timeSeries"]) > 0:
                current = data["timeSeries"][0].get("data", {})
                
                # Current conditions
                precip_mm = float(current.get("precipitation_amount_mean") or current.get("precipitation_amount_mean_deterministic") or 0)
                cloud_octas = float(current.get("cloud_area_fraction") or 4)
                humidity_pct = float(current.get("relative_humidity") or 70)
                precip_prob = float(current.get("probability_of_precipitation") or 0)
                
                # Temperature trend (next 2 hours if available)
                if len(data["timeSeries"]) > 2:
                    future_temp = data["timeSeries"][2].get("data", {}).get("air_temperature")
                    if future_temp is not None:
                        temp_trend = float(future_temp) - temp_c
        except:
            pass  # Use defaults if data unavailable
    
    # Base felt temperature with wind chill
    if temp_c < 10 and wind_ms > 1.5:
        # JAG/TI wind chill for cool conditions
        wind_factor = 1.3 * (wind_ms ** 0.16)
        felt_temp = temp_c - (wind_factor * (10 - temp_c) / 10)
    else:
        felt_temp = temp_c
    
    # Cloud cover adjustment: sunny feels 1-2°C warmer than cloudy
    if cloud_octas < 2:  # Clear
        felt_temp += 1.5
    elif cloud_octas < 4:  # Mostly clear
        felt_temp += 0.8
    elif cloud_octas > 6:  # Very cloudy
        felt_temp -= 0.5
    
    # Humidity adjustment: high humidity feels cooler
    if humidity_pct > 85:
        felt_temp -= 0.8
    elif humidity_pct < 40:
        felt_temp += 0.5
    
    # Forecast trend: if getting colder, dress warmer NOW
    if temp_trend < -2:
        felt_temp += temp_trend * 0.3  # Reduce felt temp if cooling
    
    # Base CLO for Swedish outdoor comfort
    # More conservative than previous version - Swedes dress warmer in practice
    if felt_temp >= 22:
        base_clo = 0.25 + (24 - felt_temp) * 0.04  # 0.17-0.33
    elif felt_temp >= 18:
        base_clo = 0.40 + (20 - felt_temp) * 0.04  # 0.32-0.48
    elif felt_temp >= 14:
        base_clo = 0.55 + (16 - felt_temp) * 0.05  # 0.45-0.65
    elif felt_temp >= 10:
        base_clo = 0.75 + (12 - felt_temp) * 0.055  # 0.64-0.86
    elif felt_temp >= 6:
        base_clo = 0.95 + (8 - felt_temp) * 0.06  # 0.83-1.07
    elif felt_temp >= 2:
        base_clo = 1.20 + (4 - felt_temp) * 0.07  # 1.06-1.34
    elif felt_temp >= -2:
        base_clo = 1.45 + (0 - felt_temp) * 0.08  # 1.29-1.61
    elif felt_temp >= -6:
        base_clo = 1.75 + (-4 - felt_temp) * 0.09  # 1.57-1.93
    elif felt_temp >= -10:
        base_clo = 2.10 + (-8 - felt_temp) * 0.10  # 1.92-2.30
    else:
        base_clo = 2.45 + max(-12 - felt_temp, 0) * 0.12  # 2.21+
    
    # Precipitation adjustment: rain/snow requires waterproof layer
    if precip_mm > 0.5 or precip_prob > 60:
        # Heavy rain or high probability
        base_clo += 0.15  # Need waterproof shell
    elif precip_mm > 0.1 or precip_prob > 30:
        # Light rain or moderate probability
        base_clo += 0.08
    
    # Wind penalty for exposed conditions
    if wind_ms > 5:
        base_clo += (wind_ms - 5) * 0.025  # Extra insulation needed
    
    # Activity adjustment: light activity (walking) generates extra heat
    # But less aggressive than before - Swedish practice is to dress warm
    activity_reduction = 0.08  # Reduced from 0.12
    
    final_clo = base_clo - activity_reduction
    
    return round(max(0.20, min(final_clo, 3.2)), 2)

def calculate_sleep_comfort(temp_c: float, humidity: float) -> int:
    """Calculate sleep comfort score (0-100) with enhanced humidity considerations."""
    # Optimal sleep temperature: 16-19°C
    ideal_temp = 17.5
    temp_range = 1.5
    
    # Temperature score calculation
    temp_score = 100
    temp_diff = abs(temp_c - ideal_temp)
    
    if temp_diff <= temp_range:
        # Perfect range
        temp_score = 100
    elif temp_diff <= 3:
        # Good range
        temp_score = 100 - ((temp_diff - temp_range) / 1.5) * 30
    elif temp_diff <= 5:
        # Acceptable range
        temp_score = 70 - ((temp_diff - 3) / 2) * 30
    elif temp_diff <= 8:
        # Poor range
        temp_score = 40 - ((temp_diff - 5) / 3) * 30
    else:
        # Very poor
        temp_score = 10 - min(10, (temp_diff - 8) * 2)
    
    # Humidity score with enhanced penalties
    # Optimal: 40-60% RH
    humidity_score = 100
    
    if humidity > 70:
        # High humidity disrupts sleep significantly
        if humidity > 80:
            humidity_score = 40  # Very poor
        elif humidity > 75:
            humidity_score = 60  # Poor
        else:
            humidity_score = 80  # Fair
    elif humidity < 30:
        # Dry air causes discomfort
        if humidity < 20:
            humidity_score = 50  # Very poor
        elif humidity < 25:
            humidity_score = 70  # Poor
        else:
            humidity_score = 85  # Fair
    elif 40 <= humidity <= 60:
        # Ideal range
        humidity_score = 100
    else:
        # Slightly outside ideal (30-40 or 60-70)
        humidity_score = 95
    
    # Weight: temperature 70%, humidity 30% (humidity affects sleep more than general comfort)
    final_score = (temp_score * 0.7 + humidity_score * 0.3)
    return max(0, min(100, int(final_score)))


def calculate_exercise_safety(temp_c: float, wind_ms: float, humidity: float) -> tuple[int, str]:
    """Calculate exercise safety index (0-100) adapted for Swedish climate. Returns (score, category_key)."""
    feels_like = calculate_feels_like(temp_c, wind_ms, humidity)
    
    score = 100
    category = "safe"
    
    # Extreme heat danger zones (adjusted for Swedish climate)
    if feels_like >= 35:
        score = 0
        category = "extreme_danger"
    elif feels_like >= 32:
        score = 10
        category = "extreme_risk"
    elif feels_like >= 28:
        score = 30
        category = "high_risk"
    elif feels_like >= 25:
        score = 50
        category = "caution_hot"
    elif feels_like >= 22:
        score = 70
        category = "moderate_risk"
    elif feels_like >= 18:
        score = 100
        category = "ideal"
    # Extreme cold danger zones (common in Swedish winters)
    elif feels_like <= -30:
        score = 0
        category = "extreme_danger"
    elif feels_like <= -25:
        score = 10
        category = "extreme_risk"
    elif feels_like <= -20:
        score = 25
        category = "high_risk"
    elif feels_like <= -15:
        score = 50
        category = "caution_cold"
    elif feels_like <= -10:
        score = 70
        category = "moderate_risk"
    elif feels_like <= 0:
        score = 85
        category = "cool"
    else:
        score = 95
        category = "safe"
    
    # Humidity dehydration risk
    if humidity > 85 and temp_c > 20:
        score = max(0, score - 20)
        if score > 50:
            category = "high_dehydration_risk"
        elif score > 25:
            category = "extreme_dehydration_risk"
    elif humidity > 75 and temp_c > 18:
        score = max(0, score - 15)
        if category in ["safe", "ideal"]:
            category = "caution_hydration"
    elif humidity > 70 and temp_c > 22:
        score = max(0, score - 10)
        if category in ["safe", "ideal"]:
            category = "monitor_hydration"
    
    # Very dry air risk
    if humidity < 20 and (feels_like < -5 or feels_like > 20):
        score = max(0, score - 10)
        if category in ["safe", "ideal", "cool"]:
            category = "dry_air_caution"
    
    return score, category


def calculate_absolute_humidity(temp_c: float, humidity: float) -> float:
    """Calculate absolute humidity in g/m³."""
    import math
    es = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
    e = es * (humidity / 100.0)
    ah = (e * 2.1674) / (273.15 + temp_c)
    return ah


def calculate_frost_point(temp_c: float, humidity: float) -> float | None:
    """Calculate frost point temperature using proper thermodynamic formula.
    
    Source: https://pon.fr/dzvents-alerte-givre-et-calcul-humidite-absolue/
    """
    if temp_c >= 0:
        return None
    
    import math
    
    dew_point = calculate_dew_point(temp_c, humidity)
    T = temp_c + 273.15  # Convert to Kelvin
    Td = dew_point + 273.15
    
    # Frost point calculation
    frost_point = (Td + (2671.02 / ((2954.61 / T) + 2.193665 * math.log(T) - 13.3448)) - T) - 273.15
    
    return frost_point


def get_dew_point_perception(dew_point: float) -> str:
    """Get perception category for dew point."""
    if dew_point >= 26:
        return "Severely High"
    elif dew_point >= 24:
        return "Extremely Uncomfortable"
    elif dew_point >= 21:
        return "Very Humid"
    elif dew_point >= 18:
        return "Somewhat Uncomfortable"
    elif dew_point >= 16:
        return "Comfortable"
    elif dew_point >= 13:
        return "Pleasant"
    elif dew_point >= 10:
        return "Dry"
    else:
        return "Very Dry"


def calculate_humidex(temp_c: float, humidity: float) -> float:
    """Calculate humidex."""
    dew_point = calculate_dew_point(temp_c, humidity)
    import math
    e = 6.11 * math.exp(5417.7530 * ((1 / 273.16) - (1 / (dew_point + 273.15))))
    h = 0.5555 * (e - 10.0)
    return temp_c + h


def get_humidex_perception(humidex: float) -> str:
    """Get perception category for humidex."""
    if humidex >= 54:
        return "Heat Stroke Imminent"
    elif humidex >= 46:
        return "Dangerous"
    elif humidex >= 40:
        return "Great Discomfort"
    elif humidex >= 30:
        return "Some Discomfort"
    elif humidex >= 20:
        return "Comfortable"
    else:
        return "Cool"


def calculate_relative_strain_index(temp_c: float, humidity: float) -> float | None:
    """Calculate relative strain perception (26-35°C range)."""
    if not 26 <= temp_c <= 35:
        return None
    
    import math
    dew_point = calculate_dew_point(temp_c, humidity)
    e = 6.112 * math.exp((17.67 * dew_point) / (dew_point + 243.5))
    
    rsi = (temp_c - 21) / (58 - e)
    return rsi


def get_relative_strain_perception(rsi: float | None) -> str:
    """Get perception for relative strain index."""
    if rsi is None:
        return "N/A"
    if rsi < 0.15:
        return "Comfortable"
    elif rsi < 0.25:
        return "Slight Discomfort"
    elif rsi < 0.35:
        return "Discomfort"
    elif rsi < 0.45:
        return "Great Discomfort"
    else:
        return "Extreme Discomfort"


def calculate_summer_simmer_index(temp_c: float, humidity: float) -> float:
    """Calculate summer simmer index."""
    ssi = 1.98 * (temp_c - (0.55 - 0.0055 * humidity) * (temp_c - 14.5)) - 56.83
    return ssi


def get_summer_simmer_perception(ssi: float) -> str:
    """Get perception for summer simmer index."""
    if ssi >= 65:
        return "Extreme Danger"
    elif ssi >= 55:
        return "Danger of Heat Stroke"
    elif ssi >= 50:
        return "Extreme Caution"
    elif ssi >= 40:
        return "Caution"
    elif ssi >= 25:
        return "Comfortable"
    else:
        return "Cool"


def calculate_moist_air_enthalpy(temp_c: float, humidity: float) -> float:
    """Calculate moist air enthalpy using ASHRAE 2021 standard.
    
    Uses different equations for ice (T < 0°C) and water (T >= 0°C).
    Source: ASHRAE Fundamentals 2021 pg 1.5, 1.9, 1.10
    """
    import math
    
    patm = 101325  # standard pressure at sea-level (Pa)
    c_to_k = 273.15
    T = temp_c + c_to_k
    
    # ASHRAE constants for saturation vapor pressure
    if T < c_to_k:
        # Ice equation (ASHRAE eq 5)
        c1 = -5.6745359e03
        c2 = 6.3925247e00
        c3 = -9.6778430e-03
        c4 = 6.2215701e-07
        c5 = 2.0747825e-09
        c6 = -9.4840240e-13
        c7 = 4.1635019e00
        p_ws = math.exp(c1/T + c2 + c3*T + c4*T**2 + c5*T**3 + c6*T**4 + c7*math.log(T))
    else:
        # Water equation (ASHRAE eq 6)
        c8 = -5.8002206e03
        c9 = 1.3914993e00
        c10 = -4.8640239e-02
        c11 = 4.1764768e-05
        c12 = -1.4452093e-08
        c13 = 6.5459673e00
        p_ws = math.exp(c8/T + c9 + c10*T + c11*T**2 + c12*T**3 + c13*math.log(T))
    
    # Vapor pressure (ASHRAE eq 22)
    p_w = humidity / 100 * p_ws
    
    # Humidity ratio (ASHRAE eq 20)
    W = 0.621945 * p_w / (patm - p_w)
    
    # Enthalpy (ASHRAE eq 30)
    return 1.006 * temp_c + W * (2501 + 1.86 * temp_c)


def calculate_summer_scharlau(temp_c: float, humidity: float) -> float | None:
    """Calculate summer Scharlau index (17-39°C, humidity >= 30%)."""
    if not (17 <= temp_c <= 39 and humidity >= 30):
        return None
    
    s = 0.17 * (temp_c ** 2 - 0.4 * temp_c * (100 - humidity) + 10 * (temp_c - 25))
    return s


def get_summer_scharlau_perception(s: float | None) -> str:
    """Get perception for summer Scharlau index."""
    if s is None:
        return "N/A"
    if s < 0:
        return "Cold"
    elif s < 1:
        return "Cool"
    elif s < 2:
        return "Slightly Cool"
    elif s < 3:
        return "Comfortable"
    elif s < 4:
        return "Slightly Warm"
    elif s < 5:
        return "Warm"
    else:
        return "Hot"


def calculate_winter_scharlau(temp_c: float, humidity: float, wind_ms: float) -> float | None:
    """Calculate winter Scharlau index (-5 to 6°C, humidity >= 40%)."""
    if not (-5 <= temp_c <= 6 and humidity >= 40):
        return None
    
    wind_kmh = wind_ms * 3.6
    s = (0.13 * temp_c + 0.47) * (1 - 0.04 * wind_kmh) - 0.03 * (humidity - 100)
    return s


def get_winter_scharlau_perception(s: float | None) -> str:
    """Get perception for winter Scharlau index."""
    if s is None:
        return "N/A"
    if s < -3:
        return "Very Cold"
    elif s < -2:
        return "Cold"
    elif s < -1:
        return "Cool"
    elif s < 0:
        return "Slightly Cool"
    elif s < 1:
        return "Comfortable"
    else:
        return "Warm"


def calculate_spring_scharlau(temp_c: float, humidity: float) -> float | None:
    """Calculate spring Scharlau index (6-17°C, humidity >= 30%)."""
    if not (6 <= temp_c <= 17 and humidity >= 30):
        return None
    
    s = 0.12 * (temp_c - 11.5) ** 2 - 0.02 * (humidity - 65) + (temp_c - 11.5) * 0.4
    return s


def get_spring_scharlau_perception(s: float | None) -> str:
    """Get perception for spring Scharlau index."""
    if s is None:
        return "N/A"
    if s < -2:
        return "Too Cold"
    elif s < -1:
        return "Cool"
    elif s < 0:
        return "Slightly Cool"
    elif s < 1:
        return "Comfortable"
    elif s < 2:
        return "Slightly Warm"
    else:
        return "Too Warm"


def calculate_autumn_scharlau(temp_c: float, humidity: float, wind_ms: float) -> float | None:
    """Calculate autumn Scharlau index (5-16°C, humidity >= 35%)."""
    if not (5 <= temp_c <= 16 and humidity >= 35):
        return None
    
    wind_kmh = wind_ms * 3.6
    s = 0.15 * (temp_c - 10.5) + 0.35 * (1 - wind_kmh / 20) - 0.015 * (humidity - 70)
    return s


def get_autumn_scharlau_perception(s: float | None) -> str:
    """Get perception for autumn Scharlau index."""
    if s is None:
        return "N/A"
    if s < -1.5:
        return "Cold"
    elif s < -0.5:
        return "Cool"
    elif s < 0.5:
        return "Comfortable"
    elif s < 1.5:
        return "Mild"
    else:
        return "Warm"


def get_seasonal_scharlau(temp_c: float, humidity: float, wind_ms: float, month: int) -> tuple[float | None, str, str]:
    """Get appropriate Scharlau index based on season."""
    # Determine season based on month (Northern Hemisphere)
    if month in [12, 1, 2]:
        season = "Winter"
        value = calculate_winter_scharlau(temp_c, humidity, wind_ms)
        perception = get_winter_scharlau_perception(value)
    elif month in [3, 4, 5]:
        season = "Spring"
        value = calculate_spring_scharlau(temp_c, humidity)
        perception = get_spring_scharlau_perception(value)
    elif month in [6, 7, 8]:
        season = "Summer"
        value = calculate_summer_scharlau(temp_c, humidity)
        perception = get_summer_scharlau_perception(value)
    else:  # 9, 10, 11
        season = "Autumn"
        value = calculate_autumn_scharlau(temp_c, humidity, wind_ms)
        perception = get_autumn_scharlau_perception(value)
    
    return value, perception, season


def calculate_thoms_discomfort_index(temp_c: float, humidity: float) -> float:
    """Calculate Thom's discomfort index using wet bulb temperature approximation (Stull formula).
    
    More accurate than simple formula, accounts for complex humidity effects.
    """
    import math
    
    # Wet bulb temperature approximation (Stull 2011)
    tw = (temp_c * math.atan(0.151977 * pow(humidity + 8.313659, 1/2)) +
          math.atan(temp_c + humidity) - 
          math.atan(humidity - 1.676331) +
          pow(0.00391838 * humidity, 3/2) * math.atan(0.023101 * humidity) -
          4.686035)
    
    # Thom's Discomfort Index
    tdi = 0.5 * tw + 0.5 * temp_c
    
    return tdi


def get_thoms_discomfort_perception(di: float) -> str:
    """Get perception for Thom's discomfort index."""
    if di < 15:
        return "Comfortable"
    elif di < 18:
        return "Slightly Uncomfortable"
    elif di < 21:
        return "Uncomfortable"
    elif di < 24:
        return "Very Uncomfortable"
    elif di < 27:
        return "Extremely Uncomfortable"
    else:
        return "Emergency"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    sensors = [
        SmhiPrecipitationSensor(coordinator),
        SmhiCloudsSensor(coordinator),
        SmhiThunderstormProbabilitySensor(coordinator),
        SmhiSymbolCodeSensor(coordinator),
        SmhiMetadataSensor(coordinator),
    ]
    
    # Optional calculated sensors
    if entry.options.get(CONF_ENABLE_COMFORT_SENSORS, True):
        sensors.append(SmhiFeelsLikeSensor(coordinator))
    
    if entry.options.get(CONF_ENABLE_FROST_SENSORS, True):
        sensors.append(SmhiFrostRiskSensor(coordinator))
    
    if entry.options.get(CONF_ENABLE_SLIPPERY_SENSORS, True):
        sensors.append(SmhiSlipperyRiskSensor(coordinator))
    
    if entry.options.get(CONF_ENABLE_IMPACT_SENSOR, True):
        sensors.append(SmhiWeatherImpactSensor(coordinator))
    
    if entry.options.get(CONF_ENABLE_PRACTICAL_SENSORS, True):
        sensors.extend([
            SmhiClothingInsulationSensor(coordinator),
            SmhiSleepComfortSensor(coordinator),
            SmhiExerciseSafetySensor(coordinator),
            SmhiExerciseSafetyPerceptionSensor(coordinator),
        ])
    
    if entry.options.get(CONF_ENABLE_THERMAL_SENSORS, True):
        sensors.extend([
            SmhiThermalComfortIndexSensor(coordinator),
            SmhiHumidityAnalysisSensor(coordinator),
            SmhiHeatStressLevelSensor(coordinator),
            SmhiHeatStressPerceptionSensor(coordinator),
            SmhiHumidityPerceptionSensor(coordinator),
        ])
    
    if entry.options.get(CONF_ENABLE_DETAILED_SENSORS, False):
        sensors.extend([
            SmhiFrozenPrecipitationProbabilitySensor(coordinator),
            SmhiBlackIceRiskSensor(coordinator),
            SmhiFogProbabilitySensor(coordinator),
            SmhiRapidWeatherChangeSensor(coordinator),
        ])
    
    async_add_entities(sensors)


class SmhiBaseSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": self.coordinator.entry.data.get(CONF_NAME, "SMHI"),
            "manufacturer": "SMHI",
            "model": "Open Data forecast",
            "configuration_url": "https://opendata.smhi.se/metfcst/snow1gv1/",
        }

    @property
    def available(self) -> bool:
        return bool(self.coordinator.current_payload())


class SmhiPrecipitationSensor(SmhiBaseSensor):
    _attr_name = "Precipitation"
    _attr_native_unit_of_measurement = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_device_class = SensorDeviceClass.PRECIPITATION
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_precipitation"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        value = clean_value(data.get("precipitation_amount_mean_deterministic"), parameter="precipitation_amount_mean_deterministic")
        if value is None:
            value = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        attrs = {}
        for key in (
            "precipitation_amount_mean_deterministic",
            "precipitation_amount_mean",
            "precipitation_amount_min",
            "precipitation_amount_max",
            "precipitation_amount_median",
            "probability_of_precipitation",
        ):
            attrs[key] = clean_value(data.get(key), parameter=key)
        
        frozen_prob = clean_value(data.get("probability_of_frozen_precipitation"), parameter="probability_of_frozen_precipitation")
        attrs["probability_of_frozen_precipitation"] = frozen_prob * 100 if frozen_prob is not None else None
        attrs["probability_of_frozen_precipitation_unit"] = "%"
        
        frozen_part = clean_value(data.get("precipitation_frozen_part"), parameter="precipitation_frozen_part")
        attrs["precipitation_frozen_part"] = frozen_part * 100 if frozen_part is not None else None
        attrs["precipitation_frozen_part_unit"] = "%"
        
        attrs["predominant_precipitation_type_at_surface"] = clean_value(data.get("predominant_precipitation_type_at_surface"), parameter="predominant_precipitation_type_at_surface")
        attrs["precipitation_type_description"] = ptype_description(data.get("predominant_precipitation_type_at_surface"))
        return attrs


class SmhiCloudsSensor(SmhiBaseSensor):
    _attr_name = "Clouds"
    _attr_native_unit_of_measurement = "octas"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clouds"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_clouds"

    @property
    def native_value(self):
        return clean_value(_data(self.coordinator).get("cloud_area_fraction"), parameter="cloud_area_fraction")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        attrs = {}
        for key in (
            "cloud_area_fraction",
            "low_type_cloud_area_fraction",
            "medium_type_cloud_area_fraction",
            "high_type_cloud_area_fraction",
            "cloud_base_altitude",
            "cloud_top_altitude",
        ):
            attrs[key] = clean_value(data.get(key), parameter=key)
        attrs["cloud_area_fraction_percent"] = octas_to_percent(data.get("cloud_area_fraction"))
        attrs["cloud_base_altitude_unit"] = UnitOfLength.METERS
        attrs["cloud_top_altitude_unit"] = UnitOfLength.METERS
        return attrs


class SmhiThunderstormProbabilitySensor(SmhiBaseSensor):
    _attr_name = "Thunderstorm Probability"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:flash-alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_thunderstorm_probability"

    @property
    def native_value(self):
        value = clean_value(_data(self.coordinator).get("thunderstorm_probability"), parameter="thunderstorm_probability")
        return value * 100 if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = {}
        value = self.native_value
        if value is not None:
            if value >= 70:
                attrs["risk_level"] = "Very High"
            elif value >= 50:
                attrs["risk_level"] = "High"
            elif value >= 30:
                attrs["risk_level"] = "Moderate"
            elif value >= 10:
                attrs["risk_level"] = "Low"
            else:
                attrs["risk_level"] = "Very Low"
        return attrs


class SmhiSymbolCodeSensor(SmhiBaseSensor):
    _attr_name = "Symbol Code"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_symbol_code"

    @property
    def native_value(self):
        return clean_value(_data(self.coordinator).get("symbol_code"), parameter="symbol_code")

    @property
    def icon(self) -> str:
        """Return dynamic icon based on weather condition."""
        condition = condition_from_symbol(_data(self.coordinator))
        
        # Map conditions to MDI icons
        icon_map = {
            "sunny": "mdi:weather-sunny",
            "partlycloudy": "mdi:weather-partly-cloudy",
            "cloudy": "mdi:weather-cloudy",
            "fog": "mdi:weather-fog",
            "rainy": "mdi:weather-rainy",
            "pouring": "mdi:weather-pouring",
            "lightning": "mdi:weather-lightning",
            "lightning-rainy": "mdi:weather-lightning-rainy",
            "snowy": "mdi:weather-snowy",
            "snowy-rainy": "mdi:weather-snowy-rainy",
        }
        
        return icon_map.get(condition, "mdi:weather-cloudy")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        attrs = {}
        attrs["symbol_code"] = self.native_value
        attrs["symbol_description"] = symbol_description(data.get("symbol_code"))
        attrs["home_assistant_condition"] = condition_from_symbol(data)
        return attrs


class SmhiMetadataSensor(SmhiBaseSensor):
    _attr_name = "Metadata"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:information"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_metadata"

    @property
    def native_value(self):
        return self.coordinator.current_payload().get("referenceTime") or self.coordinator.approved_reference_time

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        payload = self.coordinator.current_payload()
        coords = (payload.get("geometry") or {}).get("coordinates")
        grid = {"lon": coords[0], "lat": coords[1]} if isinstance(coords, list) and len(coords) >= 2 else None
        attrs = {}
        attrs.update({
            ATTR_APPROVED_TIME: self.coordinator.approved_time,
            ATTR_CREATED_TIME: payload.get("createdTime"),
            ATTR_REFERENCE_TIME: payload.get("referenceTime") or self.coordinator.approved_reference_time,
            ATTR_GRID_POINT: grid,
            "available_times_count": len(self.coordinator.times),
        })
        return attrs


class SmhiFeelsLikeSensor(SmhiBaseSensor):
    """Sensor for feels-like temperature."""
    _attr_name = "Comfort: Feels Like"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_feels_like"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or wind is None or humidity is None:
            return None
        
        return round(calculate_feels_like(temp, wind, humidity), 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {}
        if temp is not None and wind is not None and humidity is not None:
            wind_kmh = wind * 3.6
            wind_chill = calculate_wind_chill(temp, wind_kmh)
            heat_index = calculate_heat_index(temp, humidity)
            
            # Only include attributes when they have actual values
            if wind_chill is not None:
                attrs["wind_chill"] = round(wind_chill, 1)
            if heat_index is not None:
                attrs["heat_index"] = round(heat_index, 1)
        return attrs


class SmhiFrostRiskSensor(SmhiBaseSensor):
    """Sensor for frost risk percentage."""
    _attr_name = "Frost: Risk"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:snowflake-alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_frost_risk"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or humidity is None:
            return None
        
        dew_point = calculate_dew_point(temp, humidity)
        return calculate_frost_risk(temp, humidity, dew_point)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {}
        if temp is not None and humidity is not None:
            dew_point = calculate_dew_point(temp, humidity)
            attrs["current_temperature"] = temp
            attrs["current_dew_point"] = round(dew_point, 1)
        return attrs


class SmhiSlipperyRiskSensor(SmhiBaseSensor):
    """Sensor for slippery conditions risk."""
    _attr_name = "Slippery: Risk"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:car-brake-alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_slippery_risk"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        frozen = clean_value(data.get("precipitation_frozen_part"), parameter="precipitation_frozen_part")
        precip = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        
        if temp is None:
            return None
        
        return calculate_slippery_risk(temp, frozen, precip)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        frozen = clean_value(data.get("precipitation_frozen_part"), parameter="precipitation_frozen_part")
        precip = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        
        attrs = {}
        attrs["current_temperature"] = temp
        
        is_slippery = False
        if temp is not None and -5 <= temp <= 3:
            if frozen is not None and frozen > 0.3 and precip is not None and precip > 0.1:
                is_slippery = True
            elif -2 <= temp <= 1 and precip is not None and precip > 0.5:
                is_slippery = True
        attrs["conditions_detected"] = is_slippery
        
        return attrs


class SmhiWeatherImpactSensor(SmhiBaseSensor):
    """Sensor for overall weather impact score."""
    _attr_name = "Impact: Severity"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_weather_impact"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        precip = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        visibility = clean_value(data.get("visibility_in_air"), parameter="visibility_in_air")
        thunder = clean_value(data.get("thunderstorm_probability"), parameter="thunderstorm_probability")
        
        if temp is None or wind is None:
            return None
        
        return calculate_weather_impact(temp, wind, precip, visibility, thunder)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        attrs = {}
        attrs["current_temperature"] = clean_value(data.get("air_temperature"), parameter="air_temperature")
        attrs["current_wind_speed"] = clean_value(data.get("wind_speed"), parameter="wind_speed")
        attrs["current_precipitation"] = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        attrs["current_visibility"] = clean_value(data.get("visibility_in_air"), parameter="visibility_in_air")
        attrs["current_thunderstorm_probability"] = clean_value(data.get("thunderstorm_probability"), parameter="thunderstorm_probability")
        return attrs


class SmhiClothingInsulationSensor(SmhiBaseSensor):
    """Sensor for practical Swedish/Nordic outdoor clothing insulation."""
    _attr_name = "Practical: Clothing"
    _attr_native_unit_of_measurement = "CLO"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:hanger"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_clothing_insulation"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")

        if temp is None or wind is None:
            return None

        return round(calculate_clo_value(temp, wind, self.coordinator), 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        precip = clean_value(data.get("precipitation_amount_mean_deterministic"), parameter="precipitation_amount_mean_deterministic")
        if precip is None:
            precip = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        precip_prob = clean_value(data.get("probability_of_precipitation"), parameter="probability_of_precipitation")
        clouds = clean_value(data.get("cloud_area_fraction"), parameter="cloud_area_fraction")
        symbol = clean_value(data.get("symbol_code"), parameter="symbol_code")

        attrs: dict[str, Any] = {}
        if temp is None or wind is None:
            return attrs

        clo = calculate_clo_value(temp, wind, self.coordinator)

        attrs["climate_profile"] = "Swedish/Nordic practical outdoor clothing"
        attrs["assumption"] = "Light activity (walking/commuting), 15-30 min exposure"
        attrs["temperature"] = round(temp, 1)
        attrs["wind_speed"] = round(wind, 1)
        
        # Weather context
        if humidity is not None:
            attrs["humidity"] = round(humidity, 0)
        if clouds is not None:
            attrs["cloud_cover_octas"] = round(clouds, 0)
        if precip is not None and precip > 0:
            attrs["precipitation_mm"] = round(precip, 1)
        if precip_prob is not None and precip_prob > 0:
            attrs["precipitation_probability"] = round(precip_prob * 100 if precip_prob <= 1 else precip_prob, 0)
        if symbol:
            attrs["weather_symbol"] = symbol
        
        # Forecast trend if available
        try:
            payload = self.coordinator.current_payload()
            if payload and "timeSeries" in payload and len(payload["timeSeries"]) > 2:
                future_temp = payload["timeSeries"][2].get("data", {}).get("air_temperature")
                if future_temp is not None:
                    temp_change = round(future_temp - temp, 1)
                    if abs(temp_change) > 1:
                        attrs["temp_trend_2h"] = temp_change
        except:
            pass

        # Clothing recommendations based on CLO value
        if clo < 0.40:
            attrs["clothing_level"] = "Very light summer"
            attrs["outfit_suggestion"] = "Shorts and T-shirt, or very light summer clothing"
            attrs["example_garments"] = "Shorts, T-shirt, Sandals"
        elif clo < 0.55:
            attrs["clothing_level"] = "Light summer"
            attrs["outfit_suggestion"] = "T-shirt or thin shirt with light trousers"
            attrs["example_garments"] = "T-shirt, Light trousers, Sneakers"
        elif clo < 0.70:
            attrs["clothing_level"] = "Mild Swedish weather"
            attrs["outfit_suggestion"] = "Long sleeve shirt or thin sweater, light jacket if windy"
            attrs["example_garments"] = "Long sleeve shirt, Light sweater, Trousers"
        elif clo < 0.85:
            attrs["clothing_level"] = "Cool but normal"
            attrs["outfit_suggestion"] = "Sweater or hoodie, windproof layer if breezy"
            attrs["example_garments"] = "Hoodie, Sweater, Trousers, Closed shoes"
        elif clo < 1.00:
            attrs["clothing_level"] = "Chilly"
            attrs["outfit_suggestion"] = "Light jacket or sweater with windproof shell"
            attrs["example_garments"] = "Light jacket, Sweater, Windbreaker"
        elif clo < 1.20:
            attrs["clothing_level"] = "Cold"
            attrs["outfit_suggestion"] = "Jacket with warm layers"
            attrs["example_garments"] = "Jacket, Sweater, Scarf, Trousers"
        elif clo < 1.45:
            attrs["clothing_level"] = "Near freezing"
            attrs["outfit_suggestion"] = "Warm jacket with gloves and hat for comfort"
            attrs["example_garments"] = "Warm jacket, Gloves, Hat, Sweater"
        elif clo < 1.75:
            attrs["clothing_level"] = "Winter"
            attrs["outfit_suggestion"] = "Winter jacket with warm layers and accessories"
            attrs["example_garments"] = "Winter jacket, Warm layers, Gloves, Hat"
        elif clo < 2.10:
            attrs["clothing_level"] = "Cold winter"
            attrs["outfit_suggestion"] = "Insulated winter clothing with full accessories"
            attrs["example_garments"] = "Insulated jacket, Thermal base, Warm boots, Gloves, Hat"
        else:
            attrs["clothing_level"] = "Severe cold"
            attrs["outfit_suggestion"] = "Full winter gear - heavy insulation required"
            attrs["example_garments"] = "Heavy winter parka, Thermal layers, Insulated boots, Winter gloves, Warm hat"
        
        # Weather-specific advice
        if precip and precip > 0.3:
            attrs["weather_note"] = "Rain expected - waterproof layer recommended"
        elif precip_prob and precip_prob > 0.6:
            attrs["weather_note"] = "High chance of rain - bring waterproof"
        elif wind and wind > 7:
            attrs["weather_note"] = "Windy - windproof outer layer important"
        elif clouds is not None and clouds < 2:
            attrs["weather_note"] = "Sunny - may feel warmer in direct sun"

        if precip is not None and precip > 0:
            attrs["precipitation_note"] = "Use waterproof outer layer if you will be outside in precipitation"
        if humidity is not None and humidity > 90 and precip is not None and precip > 0:
            attrs["humidity_warning"] = "Wet clothing loses insulation; prioritise waterproof/windproof outer layer"
        if wind >= 6:
            attrs["wind_note"] = f"Wind {wind:.1f} m/s: use a windproof outer layer rather than adding too many warm layers"

        return attrs

class SmhiSleepComfortSensor(SmhiBaseSensor):
    """Sensor for sleep comfort score."""
    _attr_name = "Practical: Sleep"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:bed"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_sleep_comfort"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or humidity is None:
            return None
        
        return calculate_sleep_comfort(temp, humidity)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {}
        if temp is not None and humidity is not None:
            score = calculate_sleep_comfort(temp, humidity)
            attrs["ideal_range"] = "16-19°C"
            
            if score >= 80:
                attrs["comfort_level"] = "Excellent"
            elif score >= 60:
                attrs["comfort_level"] = "Good"
            elif score >= 40:
                attrs["comfort_level"] = "Fair"
            elif score >= 20:
                attrs["comfort_level"] = "Poor"
            else:
                attrs["comfort_level"] = "Very Poor"
        
        return attrs


class SmhiExerciseSafetySensor(SmhiBaseSensor):
    """Sensor for outdoor exercise safety index."""
    _attr_name = "Practical: Exercise"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:run"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_exercise_safety"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or wind is None or humidity is None:
            return None
        
        score, _ = calculate_exercise_safety(temp, wind, humidity)
        return score

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {}
        if temp is not None and wind is not None and humidity is not None:
            score, category_key = calculate_exercise_safety(temp, wind, humidity)
            feels_like = calculate_feels_like(temp, wind, humidity)
            
            # Translate category based on Home Assistant language
            attrs["safety_category"] = _translate(category_key, self.hass)
            attrs["feels_like_temperature"] = round(feels_like, 1)
        
        return attrs


class SmhiExerciseSafetyPerceptionSensor(SmhiBaseSensor):
    """ENUM sensor for exercise safety perception category."""
    _attr_name = "Practical: Exercise Perception"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [e.value for e in ExerciseSafetyCategory]
    _attr_icon = "mdi:run-fast"
    _attr_translation_key = "exercise_perception"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_exercise_perception"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or wind is None or humidity is None:
            return None
        
        _, category_key = calculate_exercise_safety(temp, wind, humidity)
        return category_key


class SmhiThermalComfortIndexSensor(SmhiBaseSensor):
    """Comprehensive thermal comfort sensor - auto-selects most relevant index."""
    _attr_name = "Thermal: Comfort"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer-lines"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_thermal_comfort"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        
        if temp is None or humidity is None:
            return None
        
        # Auto-select most relevant index based on conditions
        if temp >= 27:
            # Hot weather - use heat index
            hi = calculate_heat_index(temp, humidity)
            return round(hi, 1) if hi is not None else round(temp, 1)
        elif temp >= 17:
            # Warm weather - use summer comfort
            return round(calculate_humidex(temp, humidity), 1)
        elif temp >= 10:
            # Mild weather - use Thom's
            return round(calculate_thoms_discomfort_index(temp, humidity), 1)
        elif wind is not None and temp <= 16:
            # Cooler weather - use seasonal Scharlau
            from datetime import datetime
            current_month = datetime.now().month
            scharlau_value, _, _ = get_seasonal_scharlau(temp, humidity, wind, current_month)
            if scharlau_value is not None:
                return round(temp + scharlau_value, 1)
            return round(calculate_feels_like(temp, wind, humidity), 1)
        else:
            return round(temp, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        
        attrs = {}
        if temp is None or humidity is None:
            return attrs
        
        # Always calculate all indices for reference
        attrs["heat_index"] = round(hi, 1) if (hi := calculate_heat_index(temp, humidity)) is not None else None
        attrs["humidex"] = round(calculate_humidex(temp, humidity), 1)
        attrs["thoms_discomfort"] = round(calculate_thoms_discomfort_index(temp, humidity), 1)
        
        # Seasonal Scharlau
        if wind is not None:
            from datetime import datetime
            current_month = datetime.now().month
            scharlau_value, scharlau_perception, season = get_seasonal_scharlau(temp, humidity, wind, current_month)
            
            attrs["seasonal_scharlau"] = round(scharlau_value, 2) if scharlau_value is not None else None
            attrs["seasonal_scharlau_perception"] = scharlau_perception
            attrs["current_season"] = season
        
        ssi = calculate_summer_simmer_index(temp, humidity)
        attrs["summer_simmer"] = round(ssi, 1)
        attrs["summer_simmer_perception"] = get_summer_simmer_perception(ssi)
        
        rsi = calculate_relative_strain_index(temp, humidity)
        if rsi is not None:
            attrs["relative_strain"] = round(rsi, 3)
            attrs["relative_strain_perception"] = get_relative_strain_perception(rsi)
        
        attrs["thoms_perception"] = get_thoms_discomfort_perception(attrs["thoms_discomfort"])
        
        # Determine active index
        if temp >= 27:
            attrs["active_index"] = _translate("heat_index", self.hass)
        elif temp >= 17:
            attrs["active_index"] = _translate("summer_comfort", self.hass)
        elif temp >= 10:
            attrs["active_index"] = _translate("thoms_discomfort", self.hass)
        elif wind is not None and temp <= 16:
            # Keep season name in index (Scharlau is a proper name)
            attrs["active_index"] = f"{season} Scharlau"
        else:
            attrs["active_index"] = _translate("actual_temperature", self.hass)
        
        return attrs


class SmhiHumidityAnalysisSensor(SmhiBaseSensor):
    """Comprehensive humidity analysis sensor."""
    _attr_name = "Thermal: Humidity"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:water-percent"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_humidity_analysis"

    @property
    def native_value(self):
        """Return dew point as primary value."""
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or humidity is None:
            return None
        
        return round(calculate_dew_point(temp, humidity), 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {}
        if temp is None or humidity is None:
            return attrs
        
        dew_point = calculate_dew_point(temp, humidity)
        abs_humidity = calculate_absolute_humidity(temp, humidity)
        
        attrs["dew_point"] = round(dew_point, 1)
        attrs["dew_point_perception"] = get_dew_point_perception(dew_point)
        attrs["absolute_humidity"] = round(abs_humidity, 2)
        attrs["absolute_humidity_unit"] = "g/m³"
        attrs["spread"] = round(temp - dew_point, 1)
        
        frost_point = calculate_frost_point(temp, humidity)
        if frost_point is not None:
            attrs["frost_point"] = round(frost_point, 1)
        
        # Moist air enthalpy
        attrs["moist_air_enthalpy"] = round(calculate_moist_air_enthalpy(temp, humidity), 2)
        attrs["enthalpy_unit"] = "kJ/kg"
        
        # Humidity comfort assessment
        if dew_point >= 24:
            comfort_key = "oppressive"
        elif dew_point >= 21:
            comfort_key = "very_humid"
        elif dew_point >= 18:
            comfort_key = "humid"
        elif dew_point >= 13:
            comfort_key = "comfortable"
        elif dew_point >= 10:
            comfort_key = "pleasant"
        else:
            comfort_key = "dry"
        
        attrs["humidity_comfort"] = _translate(comfort_key, self.hass)
        
        return attrs


class SmhiHeatStressLevelSensor(SmhiBaseSensor):
    """Comprehensive heat stress assessment sensor."""
    _attr_name = "Thermal: Heat Stress"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:heat-wave"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_heat_stress"

    @property
    def native_value(self):
        """Return heat stress percentage (0-100, adapted for Swedish climate)."""
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or humidity is None:
            return 0
        
        # Calculate combined heat stress score (adjusted for Swedish expectations)
        stress = 0
        
        # Base temperature stress (lower thresholds for Swedish climate)
        if temp >= 35:
            # Extreme for Sweden
            stress += 100
        elif temp >= 32:
            # Very rare, very stressful
            stress += 80 + (temp - 32) * 7
        elif temp >= 28:
            # Rare hot weather
            stress += 50 + (temp - 28) * 7.5
        elif temp >= 25:
            # Hot for Swedish standards
            stress += 30 + (temp - 25) * 6.5
        elif temp >= 22:
            # Warm, starting to be uncomfortable
            stress += 15 + (temp - 22) * 5
        elif temp >= 20:
            # Warm side of comfortable
            stress += (temp - 20) * 7.5
        elif temp >= 18:
            # Comfortable to slightly warm
            stress += (temp - 18) * 2.5
        
        # Humidity multiplier (especially impactful in Swedish humid summers)
        if humidity >= 85:
            stress *= 1.4
        elif humidity >= 75:
            stress *= 1.3
        elif humidity >= 65:
            stress *= 1.2
        elif humidity >= 50:
            stress *= 1.1
        
        return min(100, int(stress))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {}
        if temp is None or humidity is None:
            return attrs
        
        # Overall risk level
        stress_pct = self.native_value
        if stress_pct >= 80:
            risk_key = "extreme_danger"
        elif stress_pct >= 60:
            risk_key = "danger"
        elif stress_pct >= 40:
            risk_key = "extreme_caution"
        elif stress_pct >= 20:
            risk_key = "caution"
        else:
            risk_key = "safe"
        
        attrs["risk_level"] = _translate(risk_key, self.hass)
        
        # Recommendations
        if stress_pct >= 60:
            rec_key = "avoid_outdoor_activity"
        elif stress_pct >= 40:
            rec_key = "limit_outdoor_activity"
        elif stress_pct >= 20:
            rec_key = "take_breaks_drink_water"
        else:
            rec_key = "normal_activity_safe"
        
        attrs["recommendation"] = _translate(rec_key, self.hass)
        
        return attrs



class SmhiHeatStressPerceptionSensor(SmhiBaseSensor):
    """ENUM sensor for heat stress risk level perception."""
    _attr_name = "Thermal: Heat Stress Perception"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [e.value for e in RiskLevel]
    _attr_icon = "mdi:sun-thermometer-outline"
    _attr_translation_key = "heat_stress_perception"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_heat_stress_perception"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or humidity is None:
            return None
        
        # Calculate heat stress percentage
        stress = 0
        if temp >= 35:
            stress += 100
        elif temp >= 32:
            stress += 80 + (temp - 32) * 7
        elif temp >= 28:
            stress += 50 + (temp - 28) * 7.5
        elif temp >= 25:
            stress += 30 + (temp - 25) * 6.5
        elif temp >= 22:
            stress += 15 + (temp - 22) * 5
        elif temp >= 20:
            stress += (temp - 20) * 7.5
        elif temp >= 18:
            stress += (temp - 18) * 2.5
        
        if humidity >= 85:
            stress *= 1.4
        elif humidity >= 75:
            stress *= 1.3
        elif humidity >= 65:
            stress *= 1.2
        elif humidity >= 50:
            stress *= 1.1
        
        stress_pct = min(100, int(stress))
        
        # Return risk level enum
        if stress_pct >= 80:
            return RiskLevel.EXTREME_DANGER
        elif stress_pct >= 60:
            return RiskLevel.DANGER
        elif stress_pct >= 40:
            return RiskLevel.EXTREME_CAUTION
        elif stress_pct >= 20:
            return RiskLevel.CAUTION
        else:
            return RiskLevel.SAFE


class SmhiHumidityPerceptionSensor(SmhiBaseSensor):
    """ENUM sensor for humidity comfort perception."""
    _attr_name = "Thermal: Humidity Perception"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [e.value for e in HumidityComfort]
    _attr_icon = "mdi:water-percent"
    _attr_translation_key = "humidity_perception"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_humidity_perception"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or humidity is None:
            return None
        
        dew_point = calculate_dew_point(temp, humidity)
        
        # Return humidity comfort enum
        if dew_point >= 24:
            return HumidityComfort.OPPRESSIVE
        elif dew_point >= 21:
            return HumidityComfort.VERY_HUMID
        elif dew_point >= 18:
            return HumidityComfort.HUMID
        elif dew_point >= 13:
            return HumidityComfort.COMFORTABLE
        elif dew_point >= 10:
            return HumidityComfort.PLEASANT
        elif dew_point >= 5:
            return HumidityComfort.DRY
        else:
            return HumidityComfort.VERY_DRY

# =============================================================================
# SAFETY & HAZARD SENSORS
# =============================================================================

class SmhiFrozenPrecipitationProbabilitySensor(SmhiBaseSensor):
    """Probability of frozen precipitation."""
    _attr_name = "Frozen Precipitation Probability"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:snowflake-alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_frozen_precip_probability"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        value = clean_value(data.get("probability_of_frozen_precipitation"), 
                          parameter="probability_of_frozen_precipitation")
        if value is not None and value <= 1:
            value = value * 100
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = {}
        value = self.native_value
        if value is not None:
            if value >= 80:
                attrs["expectation"] = "Snow/Ice very likely"
            elif value >= 60:
                attrs["expectation"] = "Snow/Ice likely"
            elif value >= 40:
                attrs["expectation"] = "Snow/Ice possible"
            elif value >= 20:
                attrs["expectation"] = "Snow/Ice unlikely"
            else:
                attrs["expectation"] = "Snow/Ice very unlikely"
        return attrs


class SmhiBlackIceRiskSensor(SmhiBaseSensor):
    """Black ice risk assessment sensor."""
    _attr_name = "Safety: Black Ice Risk"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["none", "low", "moderate", "high", "very_high"]
    _attr_icon = "mdi:snowflake-alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_black_ice_risk"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        precip_prob = clean_value(data.get("probability_of_precipitation"), parameter="probability_of_precipitation")
        precip_amount = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        
        if temp is None or humidity is None:
            return "none"
        
        dew_point = calculate_dew_point(temp, humidity)
        spread = temp - dew_point
        
        if temp > 4:
            return "none"
        
        risk_score = 0
        
        if -4 <= temp <= 2:
            if -2 <= temp <= 0:
                risk_score += 40
            elif -4 <= temp < -2 or 0 < temp <= 2:
                risk_score += 30
        elif temp < -4:
            risk_score += 20
        
        if precip_prob and precip_prob > 0:
            risk_score += min(precip_prob / 2, 30)
        
        if precip_amount and precip_amount > 0:
            risk_score += min(precip_amount * 10, 20)
        
        if humidity > 85:
            risk_score += 15
        elif humidity > 75:
            risk_score += 10
        
        if spread < 1:
            risk_score += 10
        elif spread < 2:
            risk_score += 5
        
        if risk_score >= 80:
            return "very_high"
        elif risk_score >= 60:
            return "high"
        elif risk_score >= 40:
            return "moderate"
        elif risk_score >= 20:
            return "low"
        else:
            return "none"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {}
        if temp is not None and humidity is not None:
            dew_point = calculate_dew_point(temp, humidity)
            attrs["temperature"] = temp
            attrs["dew_point"] = round(dew_point, 1)
            attrs["spread"] = round(temp - dew_point, 1)
            
            risk = self.native_value
            if risk == "very_high":
                attrs["warning"] = "Extreme black ice risk - avoid driving if possible"
            elif risk == "high":
                attrs["warning"] = "High black ice risk - drive with extreme caution"
            elif risk == "moderate":
                attrs["warning"] = "Moderate black ice risk - reduce speed"
            elif risk == "low":
                attrs["warning"] = "Low black ice risk - stay alert"
            else:
                attrs["warning"] = "No black ice risk"
        
        return attrs


class SmhiFogProbabilitySensor(SmhiBaseSensor):
    """Fog probability sensor."""
    _attr_name = "Safety: Fog Probability"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:weather-fog"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_fog_probability"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or humidity is None:
            return 0
        
        dew_point = calculate_dew_point(temp, humidity)
        spread = temp - dew_point
        
        fog_prob = 0
        
        if spread < 0.5:
            fog_prob = 95
        elif spread < 1:
            fog_prob = 80
        elif spread < 1.5:
            fog_prob = 60
        elif spread < 2:
            fog_prob = 40
        elif spread < 2.5:
            fog_prob = 25
        elif spread < 3:
            fog_prob = 15
        else:
            fog_prob = max(0, 15 - (spread - 3) * 3)
        
        if humidity > 95:
            fog_prob = min(100, fog_prob + 10)
        elif humidity > 90:
            fog_prob = min(100, fog_prob + 5)
        
        if -5 <= temp <= 15:
            fog_prob = min(100, fog_prob + 5)
        
        return int(fog_prob)
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        visibility = clean_value(data.get("visibility_in_air"), parameter="visibility_in_air")
        
        attrs = {}
        if temp is not None and humidity is not None:
            dew_point = calculate_dew_point(temp, humidity)
            attrs["temperature"] = temp
            attrs["dew_point"] = round(dew_point, 1)
            attrs["spread"] = round(temp - dew_point, 1)
            attrs["humidity"] = humidity
            
            if visibility:
                attrs["current_visibility_km"] = visibility
            
            prob = self.native_value
            if prob >= 80:
                attrs["category"] = "Very High"
                attrs["description"] = "Dense fog likely"
            elif prob >= 60:
                attrs["category"] = "High"
                attrs["description"] = "Fog likely"
            elif prob >= 40:
                attrs["category"] = "Moderate"
                attrs["description"] = "Fog possible"
            elif prob >= 20:
                attrs["category"] = "Low"
                attrs["description"] = "Patchy fog possible"
            else:
                attrs["category"] = "Very Low"
                attrs["description"] = "Fog unlikely"
        
        return attrs


class SmhiRapidWeatherChangeSensor(SmhiBaseSensor):
    """Rapid weather change detection sensor."""
    _attr_name = "Safety: Weather Change Alert"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["stable", "minor", "moderate", "significant", "severe"]
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_weather_change_alert"

    def _get_forecast_data(self, hours_ahead: int):
        """Get forecast data for specified hours ahead."""
        payload = self.coordinator.current_payload()
        series = payload.get("timeSeries") or []
        
        if not isinstance(series, list) or not series:
            return None
        
        target_index = min(hours_ahead, len(series) - 1)
        if target_index < len(series):
            item = series[target_index]
            return item.get("data") if isinstance(item, dict) else None
        return None

    @property
    def native_value(self):
        current = _data(self.coordinator)
        forecast_1h = self._get_forecast_data(1)
        forecast_3h = self._get_forecast_data(3)
        
        if not current or not forecast_1h:
            return "stable"
        
        temp_now = clean_value(current.get("air_temperature"), parameter="air_temperature")
        pressure_now = clean_value(current.get("air_pressure_at_mean_sea_level"), parameter="air_pressure_at_mean_sea_level")
        wind_now = clean_value(current.get("wind_speed"), parameter="wind_speed")
        precip_prob_now = clean_value(current.get("probability_of_precipitation"), parameter="probability_of_precipitation") or 0
        
        if temp_now is None or pressure_now is None or wind_now is None:
            return "stable"
        
        change_score = 0
        changes = []
        
        temp_1h = clean_value(forecast_1h.get("air_temperature"), parameter="air_temperature")
        pressure_1h = clean_value(forecast_1h.get("air_pressure_at_mean_sea_level"), parameter="air_pressure_at_mean_sea_level")
        wind_1h = clean_value(forecast_1h.get("wind_speed"), parameter="wind_speed")
        precip_prob_1h = clean_value(forecast_1h.get("probability_of_precipitation"), parameter="probability_of_precipitation") or 0
        
        if temp_1h is not None:
            temp_change = abs(temp_1h - temp_now)
            if temp_change > 5:
                change_score += 30
                changes.append(f"Temp: {temp_change:+.1f}°C in 1h")
            elif temp_change > 3:
                change_score += 20
                changes.append(f"Temp: {temp_change:+.1f}°C in 1h")
            elif temp_change > 2:
                change_score += 10
        
        if pressure_1h is not None:
            pressure_change = abs(pressure_1h - pressure_now)
            if pressure_change > 5:
                change_score += 25
                changes.append(f"Pressure: {pressure_change:+.1f} hPa in 1h")
            elif pressure_change > 3:
                change_score += 15
                changes.append(f"Pressure: {pressure_change:+.1f} hPa in 1h")
        
        if wind_1h is not None:
            wind_change = abs(wind_1h - wind_now)
            if wind_change > 5:
                change_score += 20
                changes.append(f"Wind: {wind_change:+.1f} m/s in 1h")
            elif wind_change > 3:
                change_score += 10
        
        precip_change = abs(precip_prob_1h - precip_prob_now)
        if precip_change > 50:
            change_score += 25
            if precip_prob_1h > precip_prob_now:
                changes.append(f"Rain starting ({precip_prob_1h:.0f}% prob)")
            else:
                changes.append(f"Rain stopping")
        elif precip_change > 30:
            change_score += 15
        
        if forecast_3h:
            temp_3h = clean_value(forecast_3h.get("air_temperature"), parameter="air_temperature")
            if temp_3h is not None and temp_1h is not None:
                temp_change_3h = abs(temp_3h - temp_now)
                if temp_change_3h > 8:
                    change_score += 20
                    changes.append(f"Temp: {temp_3h - temp_now:+.1f}°C in 3h")
        
        if change_score >= 80:
            return "severe"
        elif change_score >= 60:
            return "significant"
        elif change_score >= 40:
            return "moderate"
        elif change_score >= 20:
            return "minor"
        else:
            return "stable"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        current = _data(self.coordinator)
        forecast_1h = self._get_forecast_data(1)
        forecast_3h = self._get_forecast_data(3)
        
        attrs = {}
        
        if not current or not forecast_1h:
            return attrs
        
        temp_now = clean_value(current.get("air_temperature"), parameter="air_temperature")
        pressure_now = clean_value(current.get("air_pressure_at_mean_sea_level"), parameter="air_pressure_at_mean_sea_level")
        wind_now = clean_value(current.get("wind_speed"), parameter="wind_speed")
        
        temp_1h = clean_value(forecast_1h.get("air_temperature"), parameter="air_temperature")
        pressure_1h = clean_value(forecast_1h.get("air_pressure_at_mean_sea_level"), parameter="air_pressure_at_mean_sea_level")
        wind_1h = clean_value(forecast_1h.get("wind_speed"), parameter="wind_speed")
        
        changes = []
        
        if temp_now is not None and temp_1h is not None:
            temp_change = temp_1h - temp_now
            attrs["temp_change_1h"] = round(temp_change, 1)
            if abs(temp_change) > 2:
                changes.append(f"Temperature {temp_change:+.1f}°C")
        
        if pressure_now is not None and pressure_1h is not None:
            pressure_change = pressure_1h - pressure_now
            attrs["pressure_change_1h"] = round(pressure_change, 1)
            if abs(pressure_change) > 3:
                changes.append(f"Pressure {pressure_change:+.1f} hPa")
        
        if wind_now is not None and wind_1h is not None:
            wind_change = wind_1h - wind_now
            attrs["wind_change_1h"] = round(wind_change, 1)
            if abs(wind_change) > 3:
                changes.append(f"Wind {wind_change:+.1f} m/s")
        
        if forecast_3h:
            temp_3h = clean_value(forecast_3h.get("air_temperature"), parameter="air_temperature")
            if temp_now is not None and temp_3h is not None:
                attrs["temp_change_3h"] = round(temp_3h - temp_now, 1)
        
        attrs["detected_changes"] = changes if changes else ["No significant changes"]
        
        severity = self.native_value
        if severity == "severe":
            attrs["recommendation"] = "Extreme weather changes expected - take precautions"
        elif severity == "significant":
            attrs["recommendation"] = "Significant changes expected - be prepared"
        elif severity == "moderate":
            attrs["recommendation"] = "Moderate changes expected - stay aware"
        elif severity == "minor":
            attrs["recommendation"] = "Minor changes expected"
        else:
            attrs["recommendation"] = "Stable conditions expected"
        
        return attrs
