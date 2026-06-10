from __future__ import annotations

# tools/comm_control_tool.py
import sys
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False
STATUS_LABEL = "tool:comm_control"


def _set_comm_tools_enabled(enabled: bool) -> str:
    """Enable or disable tools with tool_genre='comm'."""
    from . import TOOL_SPECS, _RUNNERS, _register_tool_module, _sort_registered_tools
    from importlib import import_module

    comm_modules = ["teams_webhook_tool", "discord_channel_tool"]
    changed_names = []

    if enabled:
        # Load and register comm tools
        for mname in comm_modules:
            mod_name = f"uagent.tools.{mname}"
            try:
                if mod_name in sys.modules:
                    import importlib

                    mod = importlib.reload(sys.modules[mod_name])
                else:
                    mod = import_module(mod_name)

                spec = getattr(mod, "TOOL_SPEC", None)
                if isinstance(spec, dict):
                    spec["tool_level"] = 0

                if _register_tool_module(mod, mod_name):
                    func_info = spec.get("function", {})
                    tname = func_info.get("name")
                    if tname:
                        changed_names.append(tname)
            except Exception as e:
                print(
                    f"[comm_control error] Failed to load {mod_name}: {e}",
                    file=sys.stderr,
                )

        if changed_names:
            msg = _(
                "msg.comm.enabled",
                default="[tools] Enabled communication tools (comm): {names}",
                names=", ".join(changed_names),
            )

            return msg
        else:
            msg = _(
                "msg.comm.none_enabled",
                default="[tools] No communication tools were enabled.",
            )

            return msg
    else:
        # Unregister comm tools
        removed_names = []
        to_remove = []
        for spec in TOOL_SPECS:
            if not isinstance(spec, dict):
                continue
            if spec.get("tool_genre") == "comm":
                func_info = spec.get("function", {})
                tname = func_info.get("name")
                if tname:
                    to_remove.append(tname)

        for tname in to_remove:
            for i, spec in enumerate(TOOL_SPECS):
                if spec.get("function", {}).get("name") == tname:
                    TOOL_SPECS.pop(i)
                    break
            _RUNNERS.pop(tname, None)
            removed_names.append(tname)

        _sort_registered_tools()

        if removed_names:
            msg = _(
                "msg.comm.disabled",
                default="[tools] Disabled communication tools (comm): {names}",
                names=", ".join(removed_names),
            )

            return msg
        else:
            msg = _(
                "msg.comm.none_disabled",
                default="[tools] No communication tools were disabled.",
            )

            return msg


# Dummy TOOL_SPEC so this module gets loaded as a plugin
TOOL_SPEC: dict[str, Any] = {
    "tool_level": -1,  # Do not load as an LLM tool
    "type": "function",
    "function": {
        "name": "comm_control_dummy",
        "description": _(
            "tool.description",
            default="Dummy tool for comm control registration.",
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    return "dummy"
