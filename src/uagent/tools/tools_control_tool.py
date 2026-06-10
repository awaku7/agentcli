from __future__ import annotations

# tools/tools_control_tool.py
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False
STATUS_LABEL = "tool:tools_control"

# This tool registers the base ":tools" command and coordinates subcommands
# by delegating to other control tools (like comm_control and office_control)
# if they are loaded.


def handle_cmd_tools_on(arg: str, **kwargs: Any) -> Any:
    a = (arg or "").strip().lower()
    # Delegate to loaded handlers if available
    # We can look up if there are registered handlers for "tools" subcommand "on"
    # but to avoid circular dependencies or complex lookups, we can also import directly
    # or let the dynamic command system handle it.
    # However, since ":tools" is the main command, we can delegate to specific handlers.
    if a == "comm":
        try:
            from .comm_control_tool import _set_comm_tools_enabled

            return _set_comm_tools_enabled(True)
        except ImportError:
            pass
    elif a == "office":
        try:
            from .office_control_tool import _set_office_tools_enabled

            return _set_office_tools_enabled(True)
        except ImportError:
            pass
    elif a == "devel":
        try:
            from .devel_control_tool import _set_devel_tools_enabled

            return _set_devel_tools_enabled(True)
        except ImportError:
            pass

    print("Usage: :tools on [comm|office|devel]")
    from ..util_tools import CommandResult

    return CommandResult()


def handle_cmd_tools_off(arg: str, **kwargs: Any) -> Any:
    a = (arg or "").strip().lower()
    if a == "comm":
        try:
            from .comm_control_tool import _set_comm_tools_enabled

            return _set_comm_tools_enabled(False)
        except ImportError:
            pass
    elif a == "office":
        try:
            from .office_control_tool import _set_office_tools_enabled

            return _set_office_tools_enabled(False)
        except ImportError:
            pass
    elif a == "devel":
        try:
            from .devel_control_tool import _set_devel_tools_enabled

            return _set_devel_tools_enabled(False)
        except ImportError:
            pass

    print("Usage: :tools off [comm|office|devel]")
    from ..util_tools import CommandResult

    return CommandResult()


def handle_cmd_tools_list(arg: str, **kwargs: Any) -> Any:
    q = (arg or "").strip().lower()
    from . import get_tool_specs

    try:
        tool_specs = get_tool_specs() or []
        if not tool_specs:
            print(_("msg.tools.no_tools", default="[tools] No tools loaded."))
            from ..util_tools import CommandResult

            return CommandResult()

        matched = []
        for spec in tool_specs:
            fn = (spec or {}).get("function") or {}
            name = fn.get("name") or "(unknown)"
            desc = (fn.get("description") or "").strip()

            # If query is provided, filter by name or description
            if q and (q not in name.lower() and q not in desc.lower()):
                continue
            matched.append((name, desc))

        for name, desc in matched:
            if desc:
                print("- %(name)s: %(desc)s" % {"name": name, "desc": desc})
            else:
                print("- %(name)s" % {"name": name})
        print(
            _(
                "msg.tools.loaded_count",
                default="[tools] Loaded {n} tools",
                n=len(matched),
            )
        )
    except Exception as e:
        print(f"[tools error] {type(e).__name__}: {e}")

    from ..util_tools import CommandResult

    return CommandResult()


# Register dynamic subcommands under ":tools"
CMD_SPECS = [
    {
        "command": "tools",
        "subcommand": "list",
        "handler": handle_cmd_tools_list,
        "help_text": _(
            "cmd.help.tools_list",
            default="  :tools list [query]               List loaded tools, optionally filtered by name/description",
        ),
    },
    {
        "command": "tools",
        "subcommand": "on",
        "handler": handle_cmd_tools_on,
        "help_text": _(
            "cmd.help.tools_on",
            default="  :tools on comm                    Enable communication tools (Teams, Discord)\n  :tools on office                  Enable Office tools (Excel, Word, etc.)\n  :tools on devel                   Enable development tools (lint, py_compile, tests)",
        ),
    },
    {
        "command": "tools",
        "subcommand": "off",
        "handler": handle_cmd_tools_off,
        "help_text": _(
            "cmd.help.tools_off",
            default="  :tools off comm                   Disable communication tools (Teams, Discord)\n  :tools off office                 Disable Office tools (Excel, Word, etc.)\n  :tools off devel                  Disable development tools (lint, py_compile, tests)",
        ),
    },
]

# Dummy TOOL_SPEC so this module gets loaded as a plugin
TOOL_SPEC: dict[str, Any] = {
    "tool_level": -1,  # Do not load as an LLM tool
    "type": "function",
    "function": {
        "name": "tools_control_dummy",
        "description": _(
            "tool.description",
            default="Dummy tool for tools control command registration.",
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    return "dummy"
