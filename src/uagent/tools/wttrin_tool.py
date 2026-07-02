from __future__ import annotations

import requests
import warnings
from urllib3.exceptions import InsecureRequestWarning

# wttr.in の SSL 検証オフに伴う警告を抑制
warnings.simplefilter('ignore', InsecureRequestWarning)

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "tool_genre": "external",
    "type": "function", 
    "function": {
        "name": "get_weather_wttr", 
        "description": _(
            "tool.description",
            default="Get weather information from wttr.in. Supports city name or GPS coordinates.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string", 
                    "description": _(
                        "param.city.description",
                        default="City name (e.g. 'Tokyo', 'Osaka'). Ignored if lat/lon are provided.",
                    ),
                },
                "lat": {
                    "type": "number",
                    "description": _(
                        "param.lat.description",
                        default="Latitude (GPS). Must be used together with lon. More accurate than city name.",
                    ),
                },
                "lon": {
                    "type": "number",
                    "description": _(
                        "param.lon.description",
                        default="Longitude (GPS). Must be used together with lat.",
                    ),
                },
            },
        }
    }
}


def run_tool(args):
    lat = args.get("lat")
    lon = args.get("lon")
    city = args.get("city", "")

    # Determine the location string for wttr.in
    if lat is not None and lon is not None:
        location = f"{lat},{lon}"
    elif city:
        location = city
    else:
        return _(
            "err.location_required",
            default="Error: Provide a city name, or lat+lon coordinates.",
        )

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
            desc = current_cond["lang_ja"][0].get("value", _("weather.unknown", default="Unknown"))
        elif "weatherDesc" in current_cond:
            desc = current_cond["weatherDesc"][0].get("value", _("weather.unknown", default="Unknown"))

        temp_c = current_cond.get("temp_C", "?")
        feels_like = current_cond.get("FeelsLikeC", "?")
        humidity = current_cond.get("humidity", "?")

        output = []
        output.append(_("output.header", default="### Weather for {city}").format(city=display_city))
        output.append(_(
            "output.temp",
            default="- **Temp**: {temp}°C (feels like {feels}°C)",
        ).format(temp=temp_c, feels=feels_like))
        output.append(_(
            "output.condition",
            default="- **Condition**: {desc}",
        ).format(desc=desc))
        output.append(_(
            "output.humidity",
            default="- **Humidity**: {humidity}%",
        ).format(humidity=humidity))

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

                output.append(_(
                    "output.forecast_row",
                    default="- **{date}**: {min}°C / {max}°C ({desc})",
                ).format(date=date, min=min_t, max=max_t, desc=f_desc))

        return "\n".join(output)

    except requests.exceptions.RequestException as e:
        return _(
            "err.fetch",
            default="Error fetching weather data: {err}",
        ).format(err=str(e))
    except Exception as e:
        return _(
            "err.processing",
            default="Error processing data: {err}",
        ).format(err=str(e))
