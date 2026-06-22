from __future__ import annotations

# tools/genre_control_tool.py
"""Generic genre-based tool enable/disable.

Replaces individual comm_control / devel_control / office_control / iot_control
/ exec_control / external_control / media_control modules with a single file.
All named _set_*_tools_enabled() functions are re-exported for backward compat.
"""

from typing import Any

from ._genre_control_util import disable_genre_tools, enable_genre_tools
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False
STATUS_LABEL = "tool:genre_control"

_GENRE_LABELS: dict[str, str] = {
    "basic": "Basic",
    "comm": "Communication",
    "office": "Office",
    "devel": "Development",
    "iot": "IoT",
    "exec": "Execution",
    "external": "External",
    "media": "Media",
    "file": "File",
    "index": "Index",
}


def _set_genre_tools_enabled(genre: str, enabled: bool) -> str:
    """Enable or disable tools with a given tool_genre."""
    label = _GENRE_LABELS.get(genre, genre)
    if enabled:
        names = enable_genre_tools(genre)
        if names:
            return _(
                "msg.{g}.enabled".format(g=genre),
                default="[tools] Enabled {label} tools ({g}): {names}".format(
                    label=label, g=genre, names=", ".join(names)
                ),
                names=", ".join(names),
            )
        return _(
            "msg.{g}.none_enabled".format(g=genre),
            default="[tools] No {label} tools were enabled.".format(
                label=label,
            ),
        )
    else:
        names = disable_genre_tools(genre)
        if names:
            return _(
                "msg.{g}.disabled".format(g=genre),
                default="[tools] Disabled {label} tools ({g}): {names}".format(
                    label=label, g=genre, names=", ".join(names)
                ),
                names=", ".join(names),
            )
        return _(
            "msg.{g}.none_disabled".format(g=genre),
            default="[tools] No {label} tools were disabled.".format(
                label=label,
            ),
        )


# Named wrappers for backward compatibility with existing imports
def _set_basic_tools_enabled(enabled: bool) -> str:
    return _set_genre_tools_enabled("basic", enabled)


def _set_comm_tools_enabled(enabled: bool) -> str:
    return _set_genre_tools_enabled("comm", enabled)


def _set_office_tools_enabled(enabled: bool) -> str:
    return _set_genre_tools_enabled("office", enabled)


def _set_devel_tools_enabled(enabled: bool) -> str:
    return _set_genre_tools_enabled("devel", enabled)


def _set_iot_tools_enabled(enabled: bool) -> str:
    return _set_genre_tools_enabled("iot", enabled)


def _set_exec_tools_enabled(enabled: bool) -> str:
    return _set_genre_tools_enabled("exec", enabled)


def _set_external_tools_enabled(enabled: bool) -> str:
    return _set_genre_tools_enabled("external", enabled)


def _set_file_tools_enabled(enabled: bool) -> str:
    return _set_genre_tools_enabled("file", enabled)


def _set_media_tools_enabled(enabled: bool) -> str:
    return _set_genre_tools_enabled("media", enabled)


def _set_index_tools_enabled(enabled: bool) -> str:
    return _set_genre_tools_enabled("index", enabled)


# Dummy TOOL_SPEC so this module gets loaded as a plugin
TOOL_SPEC: dict[str, Any] = {
    "tool_level": -1,  # Do not load as an LLM tool
    "type": "function",
    "function": {
        "name": "genre_control_dummy",
        "description": _(
            "tool.description",
            default="Dummy tool for genre control registration.",
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    return "dummy"
