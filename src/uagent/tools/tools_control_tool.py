from __future__ import annotations

"""Tool control commands (:tools list, :tools load, :tools on/off)."""

from typing import Any

from . import get_tool_specs
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

CMD_SPECS: list[dict[str, Any]] = []


def handle_cmd_tools_load(arg: str, **kwargs: Any) -> Any:
    """Handle :tools load <name>"""
    from ..util_tools import CommandResult

    parts = (arg or "").strip().split()
    if not parts:
        print(
            _(
                "msg.tools.usage_load",
                default="Usage: :tools load <tool_name>",
            )
        )
        return CommandResult()

    # Strip --persist and its argument (no longer supported)
    clean_parts = []
    skip_next = False
    for p in parts:
        if skip_next:
            skip_next = False
            continue
        if p == "--persist":
            skip_next = True
            continue
        clean_parts.append(p)

    if not clean_parts:
        print(
            _(
                "msg.tools.usage_load",
                default="Usage: :tools load <tool_name>",
            )
        )
        return CommandResult()

    tool_name = clean_parts[0]

    try:
        from ._genre_control_util import enable_single_tool

        ok = enable_single_tool(tool_name)
        if ok:
            print(
                _(
                    "msg.tools.loaded_single",
                    default="[tools] Loaded tool: {name}",
                    name=tool_name,
                )
            )
        else:
            print(
                _(
                    "msg.tools.not_found",
                    default="[tools] Tool not found: {name}",
                    name=tool_name,
                )
            )
    except Exception as e:
        print(f"[tools error] {type(e).__name__}: {e}")

    return CommandResult()


def handle_cmd_tools_list(arg: str, **kwargs: Any) -> Any:
    q = (arg or "").strip().lower()
    from . import get_tool_specs

    specs = get_tool_specs()
    if not specs:
        print("[tools] No tools loaded.")
        from ..util_tools import CommandResult

        return CommandResult()

    names: list[str] = []
    for spec in specs:
        fn = spec.get("function", {})
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        if q and q not in name.lower():
            continue
        names.append(name)

    if not names:
        if q:
            print(
                _("msg.tools.no_match", default="[tools] No matching tools: {q}").format(
                    q=q
                )
            )
        else:
            print("[tools] No tools loaded.")
    else:
        print(
            _(
                "msg.tools.list_header",
                default="[tools] Loaded tools ({count}):",
            ).format(count=len(names))
        )
        for n in sorted(names):
            print(f"  {n}")

    from ..util_tools import CommandResult

    return CommandResult()


def _register_tools_subcommands() -> None:
    """Register subcommands under :tools."""
    global CMD_SPECS
    if CMD_SPECS:
        return

    CMD_SPECS = [
        {
            "command": "tools",
            "subcommand": "list",
            "handler": handle_cmd_tools_list,
            "help_text": _(
                "cmd.help.tools_list",
                default="  :tools list [query]  List loaded tools, optionally filtered by search terms.",
            ),
        },
        {
            "command": "tools",
            "subcommand": "load",
            "handler": handle_cmd_tools_load,
            "help_text": _(
                "cmd.help.tools_load",
                default="  :tools load <name>  Load a single tool by name.",
            ),
        },
    ]


_register_tools_subcommands()
