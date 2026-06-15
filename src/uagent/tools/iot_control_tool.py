from __future__ import annotations

# tools/iot_control_tool.py
import sys
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False
STATUS_LABEL = "tool:iot_control"


def _set_iot_tools_enabled(enabled: bool) -> str:
    """Enable or disable tools with tool_genre='iot'."""
    from . import TOOL_SPECS, _RUNNERS, _register_tool_module, _sort_registered_tools
    from importlib import import_module

    iot_modules = [
        "ble_ops_tool",
        "upnp_scan_tool",
        "upnp_igd_control_tool",
        "switchbot_cloud_list_tool",
        "switchbot_cloud_status_tool",
        "switchbot_ble_scan_tool",
        "switchbot_ble_status_tool",
        "switchbot_ble_control_tool",
        "echonet_cache_tool",
        "echonet_monitor_tool",
        "matter_controller_list_tool",
        "matter_bridge_list_tool",
        "matter_device_status_tool",
        "matter_endpoint_list_tool",
        "matter_cluster_list_tool",
        "get_geoip_tool",
    ]
    changed_names = []

    if enabled:
        for mname in iot_modules:
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
                    f"[iot_control error] Failed to load {mod_name}: {e}",
                    file=sys.stderr,
                )

        if changed_names:
            msg = _(
                "msg.iot.enabled",
                default="[tools] Enabled IoT tools (iot): {names}",
                names=", ".join(changed_names),
            )

            return msg
        msg = _(
            "msg.iot.none_enabled",
            default="[tools] No IoT tools were enabled.",
        )

        return msg

    removed_names = []
    to_remove = []
    for spec in TOOL_SPECS:
        if not isinstance(spec, dict):
            continue
        if spec.get("tool_genre") == "iot":
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
            "msg.iot.disabled",
            default="[tools] Disabled IoT tools (iot): {names}",
            names=", ".join(removed_names),
        )

        return msg
    msg = _("msg.iot.none_disabled", default="[tools] No IoT tools were disabled.")

    return msg


TOOL_SPEC: dict[str, Any] = {
    "tool_level": -1,
    "type": "function",
    "function": {
        "name": "iot_control_dummy",
        "description": _(
            "tool.description",
            default="Dummy tool for IoT tool control registration.",
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    return "dummy"
