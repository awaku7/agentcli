"""Dynamic CLI commands contributed by tool modules (``CMD_SPEC(S)``).

Split out of ``tools/__init__.py`` (speed-first plan, P0-3). This module
owns the command registry; the package re-exports the same objects.
"""

from __future__ import annotations

from typing import Any

# Dynamic commands registered by tool modules
# Structure: { "command_name": { "subcommand_name": { "handler": handler_func, "help_text": help_text_str } } }
_DYNAMIC_COMMANDS: dict[str, dict[str, dict[str, Any]]] = {}

# Cache of get_dynamic_commands_map(); invalidated whenever _DYNAMIC_COMMANDS changes.
_DYNAMIC_MAP_CACHE: dict[str, list[str]] | None = None


def _register_dynamic_commands(mod: Any) -> None:
    """Register CMD_SPEC entries, including command-only modules."""
    cmd_specs = getattr(mod, "CMD_SPECS", None)
    if not isinstance(cmd_specs, list):
        cmd_spec = getattr(mod, "CMD_SPEC", None)
        cmd_specs = [cmd_spec] if isinstance(cmd_spec, dict) else []

    changed = False
    for cmd_spec in cmd_specs:
        if not isinstance(cmd_spec, dict):
            continue
        cmd_name = cmd_spec.get("command")
        subcmd_name = cmd_spec.get("subcommand", "")
        handler = cmd_spec.get("handler")
        if not cmd_name or not callable(handler):
            continue
        help_text = cmd_spec.get("help_text", "") or ""
        help_detail = cmd_spec.get("help_detail", "") or ""
        usage = cmd_spec.get("usage", "") or ""
        if cmd_name not in _DYNAMIC_COMMANDS:
            _DYNAMIC_COMMANDS[cmd_name] = {}
        prev = _DYNAMIC_COMMANDS[cmd_name].get(subcmd_name) or {}
        _DYNAMIC_COMMANDS[cmd_name][subcmd_name] = {
            "handler": handler,
            "help_text": help_text or prev.get("help_text", ""),
            "help_detail": help_detail or prev.get("help_detail", ""),
            "usage": usage or prev.get("usage", ""),
        }
        changed = True
    if changed:
        _invalidate_dynamic_map_cache()


def handle_dynamic_command(cmd: str, arg: str, **kwargs: Any) -> Any:
    """Execute a dynamic command registered by a tool module.

    Returns:
        The result of the handler (CommandResult or bool), or None if no matching handler is found.
    """
    # Read from the package at call time so patches on
    # ``uagent.tools`` apply.
    from . import (
        _ensure_loaded,
    )

    _ensure_loaded()
    if cmd not in _DYNAMIC_COMMANDS:
        return None

    parts = arg.strip().split(maxsplit=1)
    subcmd = parts[0].lower() if parts else ""
    subarg = parts[1].strip() if len(parts) > 1 else ""

    # 0. Try two-level subcommand: "geo list" -> full key "geo list"
    if subarg:
        subarg_parts = subarg.split(maxsplit=1)
        subarg_first = subarg_parts[0]
        subarg_rest = subarg_parts[1].strip() if len(subarg_parts) > 1 else ""
        two_level_key = f"{subcmd} {subarg_first}"
        if two_level_key in _DYNAMIC_COMMANDS[cmd]:
            handler_info = _DYNAMIC_COMMANDS[cmd][two_level_key]
            return handler_info["handler"](subarg_rest, **kwargs)

    # 1. Try to match single-level subcommand
    if subcmd in _DYNAMIC_COMMANDS[cmd]:
        handler_info = _DYNAMIC_COMMANDS[cmd][subcmd]
        return handler_info["handler"](subarg, **kwargs)

    # 2. Try to match default handler (empty subcommand)
    if "" in _DYNAMIC_COMMANDS[cmd]:
        handler_info = _DYNAMIC_COMMANDS[cmd][""]
        return handler_info["handler"](arg, **kwargs)

    return None


def get_dynamic_commands_help() -> list[str]:
    """Return short help lines for all registered dynamic commands (overview).

    One compact line per top-level command. Full subcommand text is for :help <cmd>.
    """
    # Read from the package at call time so patches on
    # ``uagent.tools`` apply.
    from . import (
        _ensure_loaded,
    )

    _ensure_loaded()
    help_lines: list[str] = []
    for cmd in sorted(_DYNAMIC_COMMANDS.keys()):
        subs = _DYNAMIC_COMMANDS[cmd]
        sub_names = [k for k in sorted(subs.keys()) if k]
        if sub_names:
            # Keep overview short: show subcommand names only.
            shown = sub_names[:8]
            more = "" if len(sub_names) <= 8 else ", ..."
            help_lines.append(
                f"  :{cmd} <{'|'.join(shown)}{more}>  (dynamic; :help {cmd})"
            )
        else:
            ht = (subs.get("").get("help_text") or "").strip() if "" in subs else ""
            if ht:
                first = ht.splitlines()[0].strip()
                if not first.startswith(":"):
                    first = f":{cmd}  {first}"
                help_lines.append("  " + first if not first.startswith("  ") else first)
            else:
                help_lines.append(f"  :{cmd}  (dynamic; :help {cmd})")
    return help_lines


def _invalidate_dynamic_map_cache() -> None:
    """Drop the cached dynamic command map (call whenever _DYNAMIC_COMMANDS changes)."""
    global _DYNAMIC_MAP_CACHE
    _DYNAMIC_MAP_CACHE = None


def _reset_dynamic_command_registry() -> None:
    """Empty the registry in place (the package re-exports the same dict).

    The package calls this every time ``tools/__init__.py`` executes, so that
    ``importlib.reload(uagent.tools)`` (``:tools reload``) drops commands of
    removed plugins. This module itself stays cached across that reload.
    """
    _DYNAMIC_COMMANDS.clear()
    _invalidate_dynamic_map_cache()


def _build_dynamic_map_snapshot() -> dict[str, list[str]]:
    """Build command -> sorted subcommand map from the current registry.

    Lock-free snapshot: callers that need consistency across plugin loads
    should use get_dynamic_commands_map(block=True) instead.
    """
    result: dict[str, list[str]] = {}
    for cmd in sorted(_DYNAMIC_COMMANDS.keys()):
        subcmds = [k for k in _DYNAMIC_COMMANDS[cmd].keys() if k]
        if subcmds:
            result[cmd] = sorted(subcmds)
    return result


def get_dynamic_commands_map(*, block: bool = True) -> dict[str, list[str]]:
    """Return a mapping of command -> sorted list of subcommand names.

    The result is cached and invalidated whenever dynamic commands change.

    With block=True (default) the tool plugins are loaded on first access,
    so the returned map is complete. With block=False the map is built from
    whatever is currently registered and never blocks on the (potentially
    slow) first-time plugin import — used by interactive tab-completion so
    the prompt stays responsive while the background warmup is still loading
    heavy tool modules.
    """
    # Read from the package at call time so patches on
    # ``uagent.tools`` apply.
    from . import (
        _TOOLS_LOCK,
        _ensure_loaded,
    )

    global _DYNAMIC_MAP_CACHE
    if block:
        _ensure_loaded()
    cache = _DYNAMIC_MAP_CACHE
    if cache is not None:
        return cache
    try:
        snapshot = _build_dynamic_map_snapshot()
    except Exception:
        snapshot = {}
    if block:
        with _TOOLS_LOCK:
            if _DYNAMIC_MAP_CACHE is None:
                _DYNAMIC_MAP_CACHE = snapshot
            return _DYNAMIC_MAP_CACHE
    _DYNAMIC_MAP_CACHE = snapshot
    return snapshot


def get_dynamic_command_catalog() -> list[dict[str, Any]]:
    """Return a handler-free snapshot of registered CLI command metadata.

    Called only for trusted local Web sessions. Registered plugins are loaded
    before taking the snapshot; no command handlers are ever executed.
    """
    # Read from the package at call time so patches on
    # ``uagent.tools`` apply.
    from . import (
        _TOOLS_LOCK,
        _ensure_loaded,
    )

    _ensure_loaded()
    catalog: list[dict[str, Any]] = []
    with _TOOLS_LOCK:
        for command, subcommands in sorted(_DYNAMIC_COMMANDS.items()):
            choices = []
            for subcommand, info in sorted(subcommands.items()):
                choices.append(
                    {
                        "name": subcommand,
                        "summary": str(info.get("help_text") or ""),
                        "usage": str(info.get("usage") or ""),
                    }
                )
            catalog.append({"name": command, "subcommands": choices})
    return catalog


def get_dynamic_subcommands(cmd: str, *, block: bool = True) -> list[str]:
    """Return sorted subcommand names for one dynamic command.

    Completion-friendly: accepts ":cmd", "cmd" or mixed case. See
    get_dynamic_commands_map() for the meaning of block.
    """
    name = (cmd or "").strip().lstrip(":").lower()
    return get_dynamic_commands_map(block=block).get(name, [])


def list_dynamic_command_names() -> list[str]:
    """Return sorted top-level dynamic command names."""
    # Read from the package at call time so patches on
    # ``uagent.tools`` apply.
    from . import (
        _ensure_loaded,
    )

    _ensure_loaded()
    return sorted(_DYNAMIC_COMMANDS.keys())


def register_dynamic_command(
    command: str,
    handler: Any,
    *,
    subcommand: str = "",
    help_text: str = "",
    help_detail: str = "",
    usage: str = "",
    overwrite: bool = False,
    source: str = "",
) -> dict[str, Any]:
    """Register a dynamic ":" command/subcommand at runtime (plugins).

    Returns ok/error dict. Refuses overwrite unless overwrite=True.
    """
    # Read from the package at call time so patches on
    # ``uagent.tools`` apply.
    from . import (
        _TOOLS_LOCK,
    )

    cmd = (command or "").strip()
    sub = (subcommand or "").strip()
    if not cmd or not callable(handler):
        return {"ok": False, "error": "command and callable handler required"}

    with _TOOLS_LOCK:
        bucket = _DYNAMIC_COMMANDS.setdefault(cmd, {})
        if sub in bucket and not overwrite:
            prev_src = (bucket[sub] or {}).get("source") or ""
            return {
                "ok": False,
                "error": f"command already registered: :{cmd}"
                + (f" {sub}" if sub else ""),
                "existing_source": prev_src,
            }
        bucket[sub] = {
            "handler": handler,
            "help_text": help_text or "",
            "help_detail": help_detail or "",
            "usage": usage or "",
            "source": source or "",
        }
        _invalidate_dynamic_map_cache()
    return {"ok": True, "command": cmd, "subcommand": sub}


def unregister_dynamic_commands_by_source(source: str) -> dict[str, Any]:
    """Remove all dynamic commands registered with the given source tag."""
    # Read from the package at call time so patches on
    # ``uagent.tools`` apply.
    from . import (
        _TOOLS_LOCK,
    )

    src = (source or "").strip()
    if not src:
        return {"ok": False, "error": "source required", "removed": 0}

    removed = 0
    with _TOOLS_LOCK:
        empty_cmds: list[str] = []
        for cmd, subs in list(_DYNAMIC_COMMANDS.items()):
            for sub in list(subs.keys()):
                info = subs.get(sub) or {}
                if info.get("source") == src:
                    del subs[sub]
                    removed += 1
            if not subs:
                empty_cmds.append(cmd)
        for cmd in empty_cmds:
            _DYNAMIC_COMMANDS.pop(cmd, None)
        if removed:
            _invalidate_dynamic_map_cache()
    return {"ok": True, "removed": removed, "source": src}


def get_dynamic_command_sources() -> dict[str, str]:
    """Map \"cmd\" or \"cmd sub\" -> source tag."""
    # Read from the package at call time so patches on
    # ``uagent.tools`` apply.
    from . import (
        _TOOLS_LOCK,
    )

    out: dict[str, str] = {}
    with _TOOLS_LOCK:
        for cmd, subs in _DYNAMIC_COMMANDS.items():
            for sub, info in subs.items():
                key = f"{cmd} {sub}".strip()
                src = (info or {}).get("source") or ""
                if src:
                    out[key] = src
    return out


def get_dynamic_command_detail(cmd: str, subcmd: str | None = None) -> str | None:
    """Return detailed help for a dynamic command (and optional subcommand).

    Returns None if the command is not registered.
    """
    # Read from the package at call time so patches on
    # ``uagent.tools`` apply.
    from . import (
        _ensure_loaded,
    )

    _ensure_loaded()
    name = (cmd or "").strip().lstrip(":").lower()
    if not name or name not in _DYNAMIC_COMMANDS:
        return None

    subs = _DYNAMIC_COMMANDS[name]
    want_sub = (subcmd or "").strip().lower()

    lines: list[str] = []
    lines.append(f":{name}  (dynamic command)")

    if want_sub:
        info = subs.get(want_sub)
        if info is None:
            known = ", ".join(sorted(k for k in subs if k)) or "(none)"
            lines.append(f"Unknown subcommand: {want_sub}")
            lines.append(f"Available: {known}")
            return "\n".join(lines)
        targets = [(want_sub, info)]
    else:
        # Default handler first, then named subcommands.
        order = sorted(subs.keys(), key=lambda s: (s != "", s))
        targets = [(k, subs[k]) for k in order]

    sub_list = [k for k in sorted(subs.keys()) if k]
    if sub_list and not want_sub:
        lines.append("Subcommands: " + ", ".join(sub_list))
        lines.append("")

    for sk, info in targets:
        label = f":{name}" if not sk else f":{name} {sk}"
        lines.append(label)
        usage = (info.get("usage") or "").strip()
        detail = (info.get("help_detail") or "").strip()
        short = (info.get("help_text") or "").strip()
        if usage:
            lines.append(f"  Usage: {usage}")
        if detail:
            for dl in detail.splitlines():
                lines.append("  " + dl if dl.strip() else "")
        elif short:
            for sl in short.splitlines():
                s2 = sl.strip()
                if s2.startswith(":"):
                    lines.append("  " + s2)
                elif s2:
                    lines.append("  " + s2)
        else:
            lines.append("  (no help_text; see CMD_SPEC help_text/help_detail)")
        lines.append("")

    # Trim trailing blank
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)
