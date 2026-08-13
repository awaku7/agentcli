from __future__ import annotations


from .i18n_helper import make_tool_translator
from .location_backends import get_location as _get_location

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "tool_genre": "iot",
    "type": "function",
    "function": {
        "name": "get_current_location",
        "description": _(
            "tool.description",
            default="Get your current location (latitude, longitude) using the best available location provider. Returns coordinates with accuracy and source information.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["gps", "location", "current location"],
        ),
        "x_search_terms_en": ["gps", "location", "current location"],
        "parameters": {"type": "object", "properties": {}},
    },
}
LOAD_DISABLED_REASON = ""


def run_tool(args: dict) -> str:
    try:
        lat, lon, acc, src, ts = _get_location()
    except Exception as e:
        return _("err.generic", default="Error: Location query failed: {err}").format(
            err=str(e)
        )

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
        _("output.header", default="## Current Location"),
        _(
            "output.coords", default="- **Latitude**: {lat}\n- **Longitude**: {lon}"
        ).format(lat=lat, lon=lon),
    ]
    if accuracy_desc:
        output.append(
            _("output.accuracy", default="- **Accuracy**: {acc}").format(
                acc=accuracy_desc
            )
        )
    output.append(
        _("output.source", default="- **Source**: {src}").format(src=source_label)
    )
    if ts:
        output.append(
            _("output.timestamp", default="- **Timestamp**: {ts}").format(ts=ts)
        )

    return "\n".join(output)

