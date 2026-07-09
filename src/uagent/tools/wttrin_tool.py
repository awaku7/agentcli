from __future__ import annotations

import requests
import warnings
from urllib3.exceptions import InsecureRequestWarning

# SSL 検証オフに伴う警告を抑制
warnings.simplefilter("ignore", InsecureRequestWarning)

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "tool_genre": "external",
    "x_parallel_safe": True,
    "type": "function",
    "function": {
        "name": "get_weather_wttr",
        "description": _(
            "tool.description",
            default="Get weather information from wttr.in. Supports city name or GPS coordinates. Falls back to Open-Meteo API when wttr.in is unavailable.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["weather", "forecast", "temperature", "天気", "気温", "天気予報"],
        ),
        "x_search_terms_en": [
            "weather",
            "forecast",
            "temperature",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": _(
                        "param.city.description",
                        default="City name (e.g. 'Tokyo', 'Osaka'). REQUIRED unless lat+lon are provided.",
                    ),
                },
                "lat": {
                    "type": "number",
                    "description": _(
                        "param.lat.description",
                        default="Latitude (GPS). REQUIRED together with lon unless city is provided. More accurate than city name.",
                    ),
                },
                "lon": {
                    "type": "number",
                    "description": _(
                        "param.lon.description",
                        default="Longitude (GPS). REQUIRED together with lat unless city is provided.",
                    ),
                },
            },
            "required": [],
        },
    },
}


# --- WMO weather code to description mapping -----------------------------

WMO_CODES = {
    0: _("wmo.0", default="Clear sky"),
    1: _("wmo.1", default="Mainly clear"),
    2: _("wmo.2", default="Partly cloudy"),
    3: _("wmo.3", default="Overcast"),
    45: _("wmo.45", default="Foggy"),
    48: _("wmo.48", default="Depositing rime fog"),
    51: _("wmo.51", default="Light drizzle"),
    53: _("wmo.53", default="Moderate drizzle"),
    55: _("wmo.55", default="Dense drizzle"),
    56: _("wmo.56", default="Light freezing drizzle"),
    57: _("wmo.57", default="Dense freezing drizzle"),
    61: _("wmo.61", default="Slight rain"),
    63: _("wmo.63", default="Moderate rain"),
    65: _("wmo.65", default="Heavy rain"),
    66: _("wmo.66", default="Light freezing rain"),
    67: _("wmo.67", default="Heavy freezing rain"),
    71: _("wmo.71", default="Slight snow fall"),
    73: _("wmo.73", default="Moderate snow fall"),
    75: _("wmo.75", default="Heavy snow fall"),
    77: _("wmo.77", default="Snow grains"),
    80: _("wmo.80", default="Slight rain showers"),
    81: _("wmo.81", default="Moderate rain showers"),
    82: _("wmo.82", default="Violent rain showers"),
    85: _("wmo.85", default="Slight snow showers"),
    86: _("wmo.86", default="Heavy snow showers"),
    95: _("wmo.95", default="Thunderstorm"),
    96: _("wmo.96", default="Thunderstorm with slight hail"),
    99: _("wmo.99", default="Thunderstorm with heavy hail"),
}


def _wmo_desc(code: int) -> str:
    """Convert WMO weather code to description string."""
    return WMO_CODES.get(code, _("weather.unknown", default="Unknown"))


# --- Open-Meteo fallback -------------------------------------------------


def _fetch_openmeteo(lat: float, lon: float) -> dict | str:
    """Fetch weather from Open-Meteo API. Returns dict on success, str error."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,weathercode"
        f"&daily=temperature_2m_max,temperature_2m_min,weathercode"
        f"&timezone=auto"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _geocode_openmeteo(city: str) -> tuple[float, float, str] | str:
    """Resolve city name to (lat, lon, display_name) via Open-Meteo Geocoding API."""
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results")
    if not results:
        return _(
            "err.geocoding_failed", default="Error: Could not locate city '{city}'."
        ).format(city=city)
    r = results[0]
    lat = r["latitude"]
    lon = r["longitude"]
    display = r.get("name", city)
    admin1 = r.get("admin1", "")
    country = r.get("country", "")
    if admin1 and country:
        display = f"{display}, {admin1}, {country}"
    return lat, lon, display


def _format_openmeteo(data: dict, display_city: str) -> str:
    """Format Open-Meteo response to match wttr.in-like output."""
    current = data.get("current", {})
    daily = data.get("daily", {})

    temp = current.get("temperature_2m", "?")
    feels = current.get("apparent_temperature", "?")
    humidity = current.get("relative_humidity_2m", "?")
    wmo_code = current.get("weathercode", -1)
    desc = _wmo_desc(wmo_code)

    output = []
    output.append(
        _("output.header", default="### Weather for {city}").format(city=display_city)
    )
    output.append(
        _(
            "output.temp",
            default="- **Temp**: {temp}°C (feels like {feels}°C)",
        ).format(temp=temp, feels=feels)
    )
    output.append(
        _(
            "output.condition",
            default="- **Condition**: {desc}",
        ).format(desc=desc)
    )
    output.append(
        _(
            "output.humidity",
            default="- **Humidity**: {humidity}%",
        ).format(humidity=humidity)
    )

    times = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    codes = daily.get("weathercode", [])

    if times:
        output.append(_("output.forecast_header", default="\n--- Forecast ---"))
        for i in range(len(times)):
            date = times[i]
            max_t = max_temps[i] if i < len(max_temps) else "?"
            min_t = min_temps[i] if i < len(min_temps) else "?"
            wc = codes[i] if i < len(codes) else -1
            f_desc = _wmo_desc(wc)
            output.append(
                _(
                    "output.forecast_row",
                    default="- **{date}**: {min}°C / {max}°C ({desc})",
                ).format(date=date, min=min_t, max=max_t, desc=f_desc)
            )

    return "\n".join(output)


# --- Main entry point ----------------------------------------------------


def run_tool(args):
    lat = args.get("lat")
    lon = args.get("lon")
    city = args.get("city", "")

    if lat is None and lon is None and not city:
        return _(
            "err.location_required",
            default="Error: Provide a city name, or lat+lon coordinates.",
        )

    # --- Primary: wttr.in ---
    if lat is not None and lon is not None:
        location = f"{lat},{lon}"
    else:
        location = city

    try:
        url = f"https://wttr.in/{location}?format=j1"
        response = requests.get(url, verify=False, timeout=10)
        response.raise_for_status()

        data = response.json()
        current_cond = data.get("current_condition", [{}])[0]

        # Resolve display name from API response
        display_city = city or f"{lat},{lon}"
        if "nearest_area" in data and data["nearest_area"]:
            area = data["nearest_area"][0].get("areaName", [{}])[0].get("value")
            if area:
                display_city = area

        # Weather condition (prefer Japanese)
        desc = _("weather.unknown", default="Unknown")
        if "lang_ja" in current_cond:
            desc = current_cond["lang_ja"][0].get(
                "value", _("weather.unknown", default="Unknown")
            )
        elif "weatherDesc" in current_cond:
            desc = current_cond["weatherDesc"][0].get(
                "value", _("weather.unknown", default="Unknown")
            )

        temp_c = current_cond.get("temp_C", "?")
        feels_like = current_cond.get("FeelsLikeC", "?")
        humidity = current_cond.get("humidity", "?")

        output = []
        output.append(
            _("output.header", default="### Weather for {city}").format(
                city=display_city
            )
        )
        output.append(
            _(
                "output.temp",
                default="- **Temp**: {temp}°C (feels like {feels}°C)",
            ).format(temp=temp_c, feels=feels_like)
        )
        output.append(
            _(
                "output.condition",
                default="- **Condition**: {desc}",
            ).format(desc=desc)
        )
        output.append(
            _(
                "output.humidity",
                default="- **Humidity**: {humidity}%",
            ).format(humidity=humidity)
        )

        # Forecast
        if "weather" in data:
            output.append(_("output.forecast_header", default="\n--- Forecast ---"))
            for day in data["weather"]:
                date = day.get("date", "")
                max_t = day.get("maxtempC", "?")
                min_t = day.get("mintempC", "?")

                f_desc = ""
                hourly = day.get("hourly", [])
                if len(hourly) > 2:
                    morn = hourly[2]
                    if "lang_ja" in morn:
                        f_desc = morn["lang_ja"][0].get("value", "")
                    elif "weatherDesc" in morn:
                        f_desc = morn["weatherDesc"][0].get("value", "")

                output.append(
                    _(
                        "output.forecast_row",
                        default="- **{date}**: {min}°C / {max}°C ({desc})",
                    ).format(date=date, min=min_t, max=max_t, desc=f_desc)
                )

        return "\n".join(output)

    except requests.exceptions.RequestException as wttr_err:
        # --- Fallback: Open-Meteo ---
        fallback_source = _("err.fallback_source", default="[via Open-Meteo fallback]")
        try:
            if lat is not None and lon is not None:
                om_lat, om_lon = lat, lon
                display_city = city or f"{lat},{lon}"
            elif city:
                # Geocode the city name
                result = _geocode_openmeteo(city)
                if isinstance(result, str):
                    return result
                om_lat, om_lon, display_city = result
            else:
                return _(
                    "err.location_required",
                    default="Error: Provide a city name, or lat+lon coordinates.",
                )

            om_data = _fetch_openmeteo(om_lat, om_lon)
            if isinstance(om_data, str):
                return om_data

            output = _format_openmeteo(om_data, display_city)
            return output + "\n" + fallback_source

        except requests.exceptions.RequestException as om_err:
            return _(
                "err.fetch",
                default="Error fetching weather data: {err}",
            ).format(err=f"wttr.in: {wttr_err}; Open-Meteo: {om_err}")
        except Exception as e:
            return _(
                "err.processing",
                default="Error processing data: {err}",
            ).format(err=str(e))

    except Exception as e:
        return _(
            "err.processing",
            default="Error processing data: {err}",
        ).format(err=str(e))
