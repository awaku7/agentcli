from __future__ import annotations

# tools/comm_control_tool.py
import json
import os
import sys
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False
STATUS_LABEL = "tool:comm_control"

# This tool registers a dynamic command ":tools" with subcommands "on" and "off"
# to dynamically enable/disable communication tools (genre="comm").


def _set_comm_tools_enabled(enabled: bool) -> str:
    """Enable or disable tools with tool_genre='comm'."""
    from . import TOOL_SPECS, _RUNNERS, _register_tool_module, _sort_registered_tools
    from importlib import import_module

    pkg_dir = os.path.dirname(__file__)
    comm_modules = ["teams_webhook_tool", "discord_channel_tool"]
    changed_names = []

    if enabled:
        # Load and register comm tools
        for mname in comm_modules:
            mod_name = f"uagent.tools.{mname}"
            try:
                # Temporarily patch _register_tool_module to bypass tool_level == 1 check
                # by loading the module, modifying its tool_level to 0, and registering it.
                if mod_name in sys.modules:
                    import importlib
                    mod = importlib.reload(sys.modules[mod_name])
                else:
                    mod = import_module(mod_name)

                spec = getattr(mod, "TOOL_SPEC", None)
                if isinstance(spec, dict):
                    # Force tool_level to 0 so it registers successfully
                    spec["tool_level"] = 0

                if _register_tool_module(mod, mod_name):
                    func_info = spec.get("function", {})
                    tname = func_info.get("name")
                    if tname:
                        changed_names.append(tname)
            except Exception as e:
                print(f"[comm_control error] Failed to load {mod_name}: {e}", file=sys.stderr)

        if changed_names:
            msg = f"[tools] 通信系ツール (comm) を有効化しました: {', '.join(changed_names)}"
            print(msg)
            return msg
        else:
            msg = "[tools] 有効化された通信系ツールはありません。"
            print(msg)
            return msg
    else:
        # Unregister comm tools
        removed_names = []
        # We identify comm tools by checking their tool_genre in TOOL_SPECS
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
            # Remove from TOOL_SPECS
            for i, spec in enumerate(TOOL_SPECS):
                if spec.get("function", {}).get("name") == tname:
                    TOOL_SPECS.pop(i)
                    break
            # Remove from runners
            _RUNNERS.pop(tname, None)
            removed_names.append(tname)

        _sort_registered_tools()

        if removed_names:
            msg = f"[tools] 通信系ツール (comm) を無効化しました: {', '.join(removed_names)}"
            print(msg)
            return msg
        else:
            msg = "[tools] 無効化された通信系ツールはありません。"
            print(msg)
            return msg


def handle_cmd_tools_on(arg: str, **kwargs: Any) -> Any:
    a = (arg or "").strip().lower()
    if a == "comm":
        return _set_comm_tools_enabled(True)
    print("Usage: :tools on comm")
    from .util_tools import CommandResult
    return CommandResult()


def handle_cmd_tools_off(arg: str, **kwargs: Any) -> Any:
    a = (arg or "").strip().lower()
    if a == "comm":
        return _set_comm_tools_enabled(False)
    print("Usage: :tools off comm")
    from .util_tools import CommandResult
    return CommandResult()


# Register dynamic subcommands under ":tools"
CMD_SPECS = [
    {
        "command": "tools",
        "subcommand": "on",
        "handler": handle_cmd_tools_on,
        "help_text": "  :tools on comm                    Enable communication tools (Teams, Discord)",
    },
    {
        "command": "tools",
        "subcommand": "off",
        "handler": handle_cmd_tools_off,
        "help_text": "  :tools off comm                   Disable communication tools (Teams, Discord)",
    }
]

# We need a dummy TOOL_SPEC so this module gets loaded as a plugin
TOOL_SPEC: dict[str, Any] = {
    "tool_level": -1,  # Do not load as an LLM tool
    "type": "function",
    "function": {
        "name": "comm_control_dummy",
        "description": "Dummy tool for comm control command registration.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    return "dummy"
