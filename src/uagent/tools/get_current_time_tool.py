from __future__ import annotations

# tools/get_current_time.py
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any
import datetime
import subprocess
import sys
import os
import locale
import ctypes

BUSY_LABEL = False  # Light tool; no Busy label needed.

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "basic",
    "x_parallel_safe": True,
    "function": {
        "name": "get_current_time",
        "description": _(
            "tool.description",
            default="Return the current time and detailed date/time information (timezone, weekday, UTC time). Use this to resolve relative date expressions (e.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "current time",
                "now",
                "timezone",
                "現在時刻",
                "hora actual",
                "heure actuelle",
                "현재 시간",
                "текущее время",
            ],
        ),
        "x_search_terms_en": [
            "current time",
            "now",
            "timezone",
            "現在時刻",
            "hora actual",
            "heure actuelle",
            "현재 시간",
            "текущее время",
        ],
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}


def _get_os_ntp_info() -> str | None:
    """Get OS-level NTP sync info (Windows/macOS/Linux)."""
    try:
        platform = sys.platform
        if platform == "win32":
            # Windows: w32tm
            # Use OEM code page for console output encoding
            try:
                cp = ctypes.windll.kernel32.GetOEMCP()
                enc = f"cp{cp}"
            except Exception:
                enc = locale.getpreferredencoding()
            r = subprocess.run(
                ["w32tm", "/query", "/status"],
                capture_output=True, timeout=5
            )
            if r.returncode == 0:
                out = r.stdout.decode(enc, errors="replace").strip()
                lines = [l for l in out.splitlines() if l.strip()]
                return " | ".join(lines)
            return None
        elif platform == "linux":
            r = subprocess.run(
                ["timedatectl", "show", "--property=NTPSynchronized,Server,Timezone"],
                capture_output=True, timeout=5
            )
            if r.returncode == 0:
                out = r.stdout.decode("utf-8", errors="replace").strip()
                lines = [l for l in out.splitlines() if l.strip()]
                return " | ".join(lines)
            # fallback: ntpq
            r2 = subprocess.run(
                ["ntpq", "-p"],
                capture_output=True, timeout=5
            )
            if r2.returncode == 0 and r2.stdout.strip():
                text = r2.stdout.decode("utf-8", errors="replace").strip()
                if text:
                    return text.splitlines()[0]
            return None
        elif platform == "darwin":
            r = subprocess.run(
                ["systemsetup", "-getnetworktimeserver"],
                capture_output=True, timeout=5
            )
            if r.returncode == 0:
                out = r.stdout.decode("utf-8", errors="replace").strip()
                return out if out else None
            return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    return None


def run_tool(args: dict[str, Any]) -> str:
    # Get local time with timezone info
    now = datetime.datetime.now().astimezone()
    utc_now = datetime.datetime.now(datetime.timezone.utc)

    # Structured output for easier parsing
    res = [
        f"ISO8601 (Local): {now.isoformat()}",
        f"ISO8601 (UTC):   {utc_now.isoformat()}",
        f"Weekday:         {now.strftime('%A')}",
        f"Timezone Name:   {now.tzname()}",
        f"UTC Offset:      {now.strftime('%z')}",
        f"Year:            {now.year}",
        f"Month:           {now.month}",
        f"Day:             {now.day}",
        f"Hour:            {now.hour}",
        f"Minute:          {now.minute}",
        f"Second:          {now.second}",
    ]

    # Append OS-level NTP sync info (or N/A if unavailable)
    ntp_info = _get_os_ntp_info()
    res.append(f"NTP Sync:        {ntp_info or 'N/A'}")

    return "[get_current_time]\n" + "\n".join(res)
