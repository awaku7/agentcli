from __future__ import annotations

"""Tool control commands (:tools list, :tools load, :tools on/off)."""

from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False
STATUS_LABEL = "tool:tools_control"

TOOL_SPEC: dict[str, Any] = {
    "tool_level": -1,
    "type": "function",
    "function": {
        "name": "tools_control_dummy",
        "description": "Dummy tool for tools control registration.",
        "x_search_terms": _(
            "x_search_terms",
            default=["tools control", "tools_control", "tools", "TOOLS"],
        ),
        "x_search_terms_en": ["tools control", "tools_control", "tools", "TOOLS"],
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    return "dummy"


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


def _tool_expire_display(
    name: str,
    *,
    thr: int,
    last: object | None,
    loaded_at: object | None,
    productive_rounds: int,
) -> str:
    """Return expiry display for :tools list (productive-round timeline)."""

    def _ago(stamp: object) -> int:
        try:
            s = int(stamp)  # type: ignore[arg-type]
        except Exception:
            return thr
        if s > productive_rounds:
            return thr
        a = productive_rounds - s
        return a if a >= 0 else 0

    if last is not None:
        ago = _ago(last)
    elif loaded_at is not None:
        ago = _ago(loaded_at)
    else:
        return "-"
    expire = thr - ago
    if expire < 0:
        expire = 0
    return str(expire)


def handle_cmd_tools_list(arg: str, **kwargs: Any) -> Any:
    q = (arg or "").strip().lower()

    from . import get_tool_specs
    from ..uagent_llm import (
        _TOOL_LAST_ROUND,
        _TOOL_AUTO_UNLOAD_ROUNDS,
        _TOTAL_ROUNDS,
        _PRODUCTIVE_ROUNDS,
    )
    from ._genre_control_util import (
        _LOADED_SINGLE_TOOLS,
        is_tool_pinned,
        get_threshold,
    )

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
                _(
                    "msg.tools.no_match", default="[tools] No matching tools: {q}"
                ).format(q=q)
            )
        else:
            print("[tools] No tools loaded.")
    else:
        print(
            _(
                "msg.tools.list_header",
                default=(
                    "[tools] Loaded tools ({count}), " "total_round={r}, llm_round={p}:"
                ),
            ).format(count=len(names), r=_TOTAL_ROUNDS, p=_PRODUCTIVE_ROUNDS)
        )
        for n in sorted(names):
            if n in ("tool_catalog", "tool_load", "unload_tool"):
                print(f"  {n}  -")
                continue
            try:
                if is_tool_pinned(n):
                    print(f"  {n}  pinned")
                    continue
                thr = get_threshold(n)
            except Exception:
                thr = _TOOL_AUTO_UNLOAD_ROUNDS
            thr = thr or _TOOL_AUTO_UNLOAD_ROUNDS

            # Keep display math identical to auto-unload:
            # only productive rounds age the counter.
            if n not in _LOADED_SINGLE_TOOLS and n not in _TOOL_LAST_ROUND:
                print(f"  {n}  -")
                continue
            last = _TOOL_LAST_ROUND.get(n)
            loaded_at = (
                _LOADED_SINGLE_TOOLS.get(n) if n in _LOADED_SINGLE_TOOLS else None
            )
            if last is None and loaded_at is None:
                print(f"  {n}  -")
                continue
            print(
                f"  {n}  {_tool_expire_display(n, thr=thr, last=last, loaded_at=loaded_at, productive_rounds=_PRODUCTIVE_ROUNDS)}"
            )

    from ..util_tools import CommandResult

    return CommandResult()


def handle_cmd_tools_on(arg, **kw):
    from ..util_tools import CommandResult
    from .genre_control_tool import _set_genre_tools_enabled

    g = (arg or "").strip().lower()
    if not g:
        print("Usage: :tools on <genre>")
        return CommandResult()
    try:
        msg = _set_genre_tools_enabled(g, True)
        if msg:
            print(msg)
    except Exception as e:
        print(str(e))
    return CommandResult()


def handle_cmd_tools_off(arg, **kw):
    from ..util_tools import CommandResult
    from .genre_control_tool import _set_genre_tools_enabled

    g = (arg or "").strip().lower()
    if not g:
        print("Usage: :tools off <genre>")
        return CommandResult()
    try:
        msg = _set_genre_tools_enabled(g, False)
        if msg:
            print(msg)
    except Exception as e:
        print(str(e))
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
        {
            "command": "tools",
            "subcommand": "on",
            "handler": handle_cmd_tools_on,
            "help_text": _(
                "cmd.help.tools_on",
                default="  :tools on [genre]              Enable tools (global) or one genre",
            ),
            "usage": ":tools on [genre]",
            "help_detail": _(
                "cmd.detail.tools_on",
                default=(
                    "No genre: turn on sending tools to the LLM.\n"
                    "With genre: enable that genre and turn global tools on."
                ),
            ),
        },
        {
            "command": "tools",
            "subcommand": "off",
            "handler": handle_cmd_tools_off,
            "help_text": _(
                "cmd.help.tools_off",
                default="  :tools off [genre]             Disable tools (global) or one genre",
            ),
            "usage": ":tools off [genre]",
            "help_detail": _(
                "cmd.detail.tools_off",
                default=(
                    "No genre: turn off sending tools to the LLM.\n"
                    "With genre: disable that genre only."
                ),
            ),
        },
        {
            "command": "tools",
            "subcommand": "reload",
            "handler": handle_cmd_tools_reload,
            "help_text": _(
                "cmd.help.tools_reload",
                default="  :tools reload                    Reload all tool code from disk.",
            ),
        },
        {
            "command": "tools",
            "subcommand": "output",
            "handler": handle_cmd_tools_output,
            "help_text": _(
                "cmd.help.tools_output",
                default="  :tools output                     Toggle display of tool execution results",
            ),
        },
    ]


def handle_cmd_tools_reload(arg: str, **kw: Any) -> Any:
    """Handle :tools reload - reload all tool code from disk."""
    from ..util_tools import CommandResult

    try:
        import importlib
        import sys

        mod = sys.modules.get("uagent.tools") or __import__("uagent.tools")
        importlib.reload(mod)
        print(
            _(
                "msg.tools.reloaded",
                default="[tools] System reloaded successfully. All tools updated with latest code.",
            )
        )
    except Exception as e:
        print(f"[tools error] Reload failed: {type(e).__name__}: {e}")
    return CommandResult()


def handle_cmd_tools_output(arg: str, **kw: Any) -> Any:
    """Handle :tools output - toggle display of tool execution results."""
    from ..util_tools import CommandResult

    core = kw.get("core")
    if core is None:
        print("[tools error] core not available")
        return CommandResult()

    core.show_tool_output = not core.show_tool_output
    state = "ON" if core.show_tool_output else "OFF"
    print(
        _(
            "msg.tools.output_state",
            default="[tools] Tool output display is now {state}",
        ).format(state=state)
    )
    return CommandResult()


_register_tools_subcommands()
