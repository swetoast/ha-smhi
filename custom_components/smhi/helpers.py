from __future__ import annotations
from typing import Any
from homeassistant.util import dt as dt_util
from .const import MISSING_VALUE, PRECIP_FROZEN_NO_PRECIP_VALUE

SYMBOL_TO_CONDITION = {1:"sunny",2:"sunny",3:"partlycloudy",4:"partlycloudy",5:"cloudy",6:"cloudy",7:"fog",8:"rainy",9:"rainy",10:"pouring",11:"lightning-rainy",12:"snowy-rainy",13:"snowy-rainy",14:"snowy-rainy",15:"snowy",16:"snowy",17:"snowy",18:"rainy",19:"rainy",20:"pouring",21:"lightning",22:"snowy-rainy",23:"snowy-rainy",24:"snowy-rainy",25:"snowy",26:"snowy",27:"snowy"}
SYMBOL_MAP = {1:"Clear sky",2:"Nearly clear sky",3:"Variable cloudiness",4:"Halfclear sky",5:"Cloudy sky",6:"Overcast",7:"Fog",8:"Light rain showers",9:"Moderate rain showers",10:"Heavy rain showers",11:"Thunderstorm",12:"Light sleet showers",13:"Moderate sleet showers",14:"Heavy sleet showers",15:"Light snow showers",16:"Moderate snow showers",17:"Heavy snow showers",18:"Light rain",19:"Moderate rain",20:"Heavy rain",21:"Thunder",22:"Light sleet",23:"Moderate sleet",24:"Heavy sleet",25:"Light snowfall",26:"Moderate snowfall",27:"Heavy snowfall"}
PTYPE_MAP = {0:"No precipitation",1:"Rain",2:"Thunderstorm",3:"Freezing rain",4:"Mixed/ice",5:"Snow",6:"Wet snow",7:"Mixture of rain and snow",8:"Ice pellets",9:"Graupel",10:"Hail",11:"Drizzle",12:"Freezing drizzle"}

def clean_value(value: Any, *, parameter: str | None = None) -> Any:
    if value is None: return None
    if isinstance(value, (int, float)) and value == MISSING_VALUE: return None
    if parameter == "precipitation_frozen_part" and value == PRECIP_FROZEN_NO_PRECIP_VALUE: return None
    return value

def octas_to_percent(value: Any) -> int | None:
    value = clean_value(value)
    if value is None: return None
    try: return int(round((float(value) / 8.0) * 100.0))
    except (TypeError, ValueError): return None

def condition_from_symbol(data: dict[str, Any]) -> str | None:
    code = clean_value(data.get("symbol_code"), parameter="symbol_code")
    try: return SYMBOL_TO_CONDITION.get(int(code)) if code is not None else None
    except (TypeError, ValueError): return None

def symbol_description(value: Any) -> str | None:
    value = clean_value(value, parameter="symbol_code")
    try: return SYMBOL_MAP.get(int(value)) if value is not None else None
    except (TypeError, ValueError): return None

def ptype_description(value: Any) -> str | None:
    value = clean_value(value, parameter="predominant_precipitation_type_at_surface")
    try: return PTYPE_MAP.get(int(value)) if value is not None else None
    except (TypeError, ValueError): return None

def current_item_from_series(series: list[dict[str, Any]]) -> dict[str, Any] | None:
    now = dt_util.utcnow()
    fallback = None
    for item in series:
        parsed = dt_util.parse_datetime(item.get("time")) if item.get("time") else None
        if parsed is None: continue
        parsed = dt_util.as_utc(parsed)
        if parsed >= now: return item
        fallback = item
    return fallback

def current_data_from_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload: return {}
    series = payload.get("timeSeries") or []
    if not isinstance(series, list): return {}
    item = current_item_from_series(series)
    data = (item or {}).get("data") or {}
    return data if isinstance(data, dict) else {}

def grid_point_from_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    coords = ((payload or {}).get("geometry") or {}).get("coordinates")
    return {"lon": coords[0], "lat": coords[1]} if isinstance(coords, list) and len(coords) >= 2 else None
