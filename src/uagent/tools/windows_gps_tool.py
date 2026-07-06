from __future__ import annotations

import asyncio
import os
import sys

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

if sys.platform == "win32":
    TOOL_SPEC = {
        "tool_genre": "iot",
        "type": "function",
        "function": {
            "name": "get_windows_gps",
            "description": _(
                "tool.description",
                default="Get your current GPS location (latitude, longitude) using the GPS sensor. High precision, returns exact coordinates with accuracy info. Use this when the user asks for their current position, location, or GPS coordinates.",
            ),
            "x_search_terms": _(
                "x_search_terms",
                default=[
                    "location",
                    "現在地",
                ],
            ),
            "x_search_terms_en": [
                "location",
                "current location",
            ],
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    }
    LOAD_DISABLED_REASON = ""
else:
    TOOL_SPEC = None
    LOAD_DISABLED_REASON = "This tool requires Windows (win32 platform)."


def run_tool(args: dict) -> str:
    if os.name != "nt":
        return _("err.not_windows", default="Error: Windows Location API is only available on Windows.")

    try:
        import importlib.util as _iu
        if _iu.find_spec("winrt.windows.devices.geolocation") is None:
            raise ImportError
    except ImportError:
        return _(
            "err.no_winrt",
            default="Error: 'winrt-Windows.Devices.Geolocation' package is not installed. Run: pip install winrt-Windows.Devices.Geolocation",
        )

    try:
        lat, lon, acc, src, ts = _get_location()
    except Exception as e:
        msg = str(e)
        if "Access is denied" in msg or "access" in msg.lower():
            return _(
                "err.location_denied",
                default="Error: Location access denied. Enable location services in Windows Settings > Privacy & security > Location, and allow desktop apps to access location.",
            )
        return _("err.generic", default="Error: Location query failed: {err}").format(err=msg)

    # Build readable output with accuracy description
    accuracy_desc = ""
    if acc is not None:
        try:
            acc_m = float(acc)
            if acc_m < 10:
                accuracy_desc = _("acc.high", default="High precision")
            elif acc_m < 50:
                accuracy_desc = _("acc.medium", default="Medium precision")
            elif acc_m < 500:
                accuracy_desc = _("acc.low", default="Low precision")
            else:
                accuracy_desc = _("acc.very_low", default="Very low precision")
            accuracy_desc += f" ({acc_m:.0f}m)"
        except ValueError:
            accuracy_desc = f"\u00b1{acc}m"

    source_label = _("src.unknown", default="Unknown")
    if src:
        src_map = {
            "CELLULAR": _("src.cellular", default="Cellular"),
            "SATELLITE": _("src.satellite", default="GPS/Satellite"),
            "WI_FI": _("src.wifi", default="WiFi positioning"),
            "IP": _("src.ip", default="IP geolocation"),
            "NMEA": _("src.nmea", default="NMEA/GPS"),
            "OBFUSCATED": _("src.obfuscated", default="Obfuscated"),
        }
        source_label = src_map.get(src.upper(), src)

    output = [
        _("output.header", default="## Windows GPS Location"),
        _("output.coords", default="- **Latitude**: {lat}\n- **Longitude**: {lon}").format(lat=lat, lon=lon),
    ]
    if accuracy_desc:
        output.append(_("output.accuracy", default="- **Accuracy**: {acc}").format(acc=accuracy_desc))
    output.append(_("output.source", default="- **Source**: {src}").format(src=source_label))
    if ts:
        output.append(_("output.timestamp", default="- **Timestamp**: {ts}").format(ts=ts))

    return "\n".join(output)


def _get_location():
    """Get GPS location using winrt and return (lat, lon, accuracy, source, timestamp)."""
    from winrt.windows.devices.geolocation import Geolocator

    locator = Geolocator()
    pos = asyncio.run(locator.get_geoposition_async())
    coord = pos.coordinate
    lat = coord.point.position.latitude
    lon = coord.point.position.longitude
    acc = coord.accuracy
    src = coord.position_source.name if coord.position_source else None
    ts = coord.timestamp.isoformat() if coord.timestamp else None
    return lat, lon, acc, src, ts
