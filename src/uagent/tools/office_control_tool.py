from __future__ import annotations

# tools/office_control_tool.py
import json
import os
import sys
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False
STATUS_LABEL = "tool:office_control"

def _set_office_tools_enabled(enabled: bool) -> str:
    """Enable or disable tools with tool_genre='office'."""
    from . import TOOL_SPECS, _RUNNERS, _register_tool_module, _sort_registered_tools
    from importlib import import_module

    pkg_dir = os.path.dirname(__file__)
    office_modules = ["excel_ops_tool", "exstruct_tool", "recalc_excel_tool", "document_extract_tool", "read_pptx_pdf_tool"]
    changed_names = []

    if enabled:
        # Load and register office tools
        for mname in office_modules:
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
                print(f"[office_control error] Failed to load {mod_name}: {e}", file=sys.stderr)

        if changed_names:
            msg = _("msg.office.enabled", default="[tools] Enabled Office tools (office): {names}", names=", ".join(changed_names))
            
            return msg
        else:
            msg = _("msg.office.none_enabled", default="[tools] No Office tools were enabled.")
            
            return msg
    else:
        # Unregister office tools
        removed_names = []
        to_remove = []
        for spec in TOOL_SPECS:
            if not isinstance(spec, dict):
                continue
            if spec.get("tool_genre") == "office":
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
            msg = _("msg.office.disabled", default="[tools] Disabled Office tools (office): {names}", names=", ".join(removed_names))
            
            return msg
        else:
            msg = _("msg.office.none_disabled", default="[tools] No Office tools were disabled.")
            
            return msg

# Dummy TOOL_SPEC so this module gets loaded as a plugin
TOOL_SPEC: dict[str, Any] = {
    "tool_level": -1,  # Do not load as an LLM tool
    "type": "function",
    "function": {
        "name": "office_control_dummy",
        "description": _(
            "tool.description",
            default="Dummy tool for office control registration.",
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

def run_tool(args: dict[str, Any]) -> str:
    return "dummy"
