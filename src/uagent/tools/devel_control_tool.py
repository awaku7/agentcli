from __future__ import annotations

# tools/devel_control_tool.py
import sys
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False
STATUS_LABEL = "tool:devel_control"


def _set_devel_tools_enabled(enabled: bool) -> str:
    """Enable or disable tools with tool_genre='devel'."""
    from . import TOOL_SPECS, _RUNNERS, _register_tool_module, _sort_registered_tools
    from importlib import import_module

    devel_modules = [
        "binary_edit_tool",
        "git_ops_tool",
        "lint_format_tool",
        "playwright_inspector_tool",
        "python_compile_tool",
        "run_tests_tool",
        "system_reload_tool",
    ]
    changed_names = []

    if enabled:
        for mname in devel_modules:
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
                    f"[devel_control error] Failed to load {mod_name}: {e}",
                    file=sys.stderr,
                )

        if changed_names:
            msg = _(
                "msg.devel.enabled",
                default="[tools] Enabled development tools (devel): {names}",
                names=", ".join(changed_names),
            )

            return msg
        msg = _(
            "msg.devel.none_enabled",
            default="[tools] No development tools were enabled.",
        )

        return msg

    removed_names = []
    to_remove = []
    for spec in TOOL_SPECS:
        if not isinstance(spec, dict):
            continue
        if spec.get("tool_genre") == "devel":
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
            "msg.devel.disabled",
            default="[tools] Disabled development tools (devel): {names}",
            names=", ".join(removed_names),
        )

        return msg
    msg = _(
        "msg.devel.none_disabled", default="[tools] No development tools were disabled."
    )

    return msg


TOOL_SPEC: dict[str, Any] = {
    "tool_level": -1,
    "type": "function",
    "function": {
        "name": "devel_control_dummy",
        "description": _(
            "tool.description",
            default="Dummy tool for development tool control registration.",
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    return "dummy"
