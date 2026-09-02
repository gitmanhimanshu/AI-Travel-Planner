"""Weather lookup with a graceful, never-fatal failure mode.

Two backends:
  * Open-Meteo  - key-less, used by default (geocoding + forecast).
  * OpenWeatherMap - used when WEATHER_API_KEY is set.

Any failure returns {"available": False, "reason": ...} so the UI can simply
hide the weather card instead of breaking the page.
"""

import logging
import time

import requests
from flask import current_app

from app.services.destinations_data import find_by_name

log = logging.getLogger(__name__)

_CACHE = {}
_CACHE_TTL_SECONDS = 30 * 60

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OWM_URL = "https://api.openweathermap.org/data/2.5/forecast"

# https://open-meteo.com/en/docs - WMO weather interpretation codes
WMO_CODES = {
    0: ("Clear sky", "bi-sun"),
    1: ("Mainly clear", "bi-sun"),
    2: ("Partly cloudy", "bi-cloud-sun"),
    3: ("Overcast", "bi-clouds"),
    45: ("Fog", "bi-cloud-fog"),
    48: ("Freezing fog", "bi-cloud-fog"),
    51: ("Light drizzle", "bi-cloud-drizzle"),
    53: ("Drizzle", "bi-cloud-drizzle"),
    55: ("Heavy drizzle", "bi-cloud-drizzle"),
    61: ("Light rain", "bi-cloud-rain"),
    63: ("Rain", "bi-cloud-rain"),
    65: ("Heavy rain", "bi-cloud-rain-heavy"),
    71: ("Light snow", "bi-snow"),
    73: ("Snow", "bi-snow"),
    75: ("Heavy snow", "bi-snow"),
    80: ("Rain showers", "bi-cloud-rain"),
    81: ("Rain showers", "bi-cloud-rain"),
    82: ("Violent rain showers", "bi-cloud-rain-heavy"),
    95: ("Thunderstorm", "bi-cloud-lightning-rain"),
    96: ("Thunderstorm with hail", "bi-cloud-lightning-rain"),
    99: ("Thunderstorm with hail", "bi-cloud-lightning-rain"),
}


def get_weather(destination):
    """Return current conditions plus a short forecast for `destination`."""
    destination = (destination or "").strip()
    if not destination:
        return _unavailable("No destination given.")

    key = destination.lower()
    cached = _CACHE.get(key)
    if cached and (time.time() - cached["at"]) < _CACHE_TTL_SECONDS:
        return cached["data"]

    timeout = current_app.config.get("WEATHER_TIMEOUT_SECONDS", 8)
    api_key = current_app.config.get("WEATHER_API_KEY")

    try:
        place = _geocode(destination, timeout)
        if not place:
            return _unavailable("We could not find that place on the map.")
        if api_key:
            data = _openweathermap(place, api_key, timeout)
        else:
            data = _open_meteo(place, timeout)
    except requests.RequestException as exc:
        log.info("Weather lookup failed for %s: %s", destination, exc)
        return _unavailable("The weather service is unreachable right now.")
    except (ValueError, KeyError, TypeError) as exc:
        log.warning("Unexpected weather payload for %s: %s", destination, exc)
        return _unavailable("The weather service returned unexpected data.")

    _CACHE[key] = {"at": time.time(), "data": data}
    return data


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------
def _geocode(destination, timeout):
    # Curated destinations carry their own coordinates, so "Goa" resolves to
    # Goa in India rather than to whatever a fuzzy geocoder ranks first.
    known = find_by_name(destination)
    if known and known.get("coords"):
        return {
            "lat": known["coords"][0],
            "lon": known["coords"][1],
            "label": known["name"] + ", " + known["country"],
        }

    response = requests.get(
        GEOCODE_URL,
        params={"name": destination, "count": 5, "language": "en", "format": "json"},
        timeout=timeout,
    )
    response.raise_for_status()
    results = (response.json() or {}).get("results") or []
    if not results:
        return None
    # Several places share a name. Prefer an exact match on the name the
    # user typed, then the largest of those; otherwise take the top hit.
    query = destination.strip().lower()
    exact = [item for item in results if (item.get("name") or "").lower() == query]
    top = max(exact or results[:1], key=lambda item: item.get("population") or 0)
    label = ", ".join(
        part for part in [top.get("name"), top.get("admin1"), top.get("country")] if part
    )
    return {"lat": top["latitude"], "lon": top["longitude"], "label": label}


def _open_meteo(place, timeout):
    response = requests.get(
        FORECAST_URL,
        params={
            "latitude": place["lat"],
            "longitude": place["lon"],
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": 7,
            "timezone": "auto",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json() or {}
    current = payload.get("current") or {}
    daily = payload.get("daily") or {}

    description, icon = WMO_CODES.get(int(current.get("weather_code") or 0), ("Unknown", "bi-cloud"))

    forecast = []
    dates = daily.get("time") or []
    for index, day in enumerate(dates[:7]):
        code = (daily.get("weather_code") or [0])[index]
        text, day_icon = WMO_CODES.get(int(code or 0), ("Unknown", "bi-cloud"))
        forecast.append(
            {
                "date": day,
                "description": text,
                "icon": day_icon,
                "temp_max": _round(daily.get("temperature_2m_max", [None])[index]),
                "temp_min": _round(daily.get("temperature_2m_min", [None])[index]),
                "rain_probability": _round(
                    (daily.get("precipitation_probability_max") or [None] * len(dates))[index]
                ),
            }
        )

    return {
        "available": True,
        "source": "Open-Meteo",
        "location": place["label"],
        "current": {
            "temperature": _round(current.get("temperature_2m")),
            "humidity": _round(current.get("relative_humidity_2m")),
            "wind_speed": _round(current.get("wind_speed_10m")),
            "description": description,
            "icon": icon,
        },
        "forecast": forecast,
    }


def _openweathermap(place, api_key, timeout):
    response = requests.get(
        OWM_URL,
        params={
            "lat": place["lat"],
            "lon": place["lon"],
            "appid": api_key,
            "units": "metric",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    entries = (response.json() or {}).get("list") or []
    if not entries:
        return _unavailable("No forecast data was returned.")

    first = entries[0]
    by_day = {}
    for entry in entries:
        day = entry["dt_txt"][:10]
        bucket = by_day.setdefault(
            day,
            {
                "date": day,
                "description": entry["weather"][0]["description"].title(),
                "icon": "bi-cloud-sun",
                "temp_max": entry["main"]["temp_max"],
                "temp_min": entry["main"]["temp_min"],
                "rain_probability": round(float(entry.get("pop") or 0) * 100),
            },
        )
        bucket["temp_max"] = max(bucket["temp_max"], entry["main"]["temp_max"])
        bucket["temp_min"] = min(bucket["temp_min"], entry["main"]["temp_min"])
        bucket["rain_probability"] = max(
            bucket["rain_probability"], round(float(entry.get("pop") or 0) * 100)
        )

    forecast = []
    for bucket in list(by_day.values())[:7]:
        bucket["temp_max"] = _round(bucket["temp_max"])
        bucket["temp_min"] = _round(bucket["temp_min"])
        forecast.append(bucket)

    return {
        "available": True,
        "source": "OpenWeatherMap",
        "location": place["label"],
        "current": {
            "temperature": _round(first["main"]["temp"]),
            "humidity": _round(first["main"].get("humidity")),
            "wind_speed": _round((first.get("wind") or {}).get("speed")),
            "description": first["weather"][0]["description"].title(),
            "icon": "bi-cloud-sun",
        },
        "forecast": forecast,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _round(value):
    try:
        return round(float(value))
    except (TypeError, ValueError):
        return None


def _unavailable(reason):
    return {"available": False, "reason": reason, "current": None, "forecast": []}
