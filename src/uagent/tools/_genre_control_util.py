from __future__ import annotations

"""Shared utility for genre-based tool enable/disable.

Replaces hardcoded module lists in genre control tools with dynamic discovery.
Control tools call enable_genre_tools(genre) / disable_genre_tools(genre)
and format their own i18n messages.
"""

import importlib
import os
import pkgutil
import sys
from typing import Any

# Track which genres are currently enabled (persists across plugin reloads)
_ENABLED_GENRES: set[str] = set()

# Track individually loaded tools and remaining uses (persists across plugin reloads)
# value: remaining uses (-1 = unlimited, 0 = expired, >0 = countdown)
_LOADED_SINGLE_TOOLS: dict[str, int] = {}


def _find_tool_modules() -> list[tuple[str, Any]]:
    """Return (module_name, module) pairs for all discoverable tool modules."""
    pkg_dir = os.path.dirname(__file__)
    results: list[tuple[str, Any]] = []
    for m in pkgutil.iter_modules([pkg_dir]):
        mname = m.name
        # Skip utility/private modules and non-tool files
        if mname.startswith("_") or mname in ("context",):
            continue
        if not mname.endswith("_tool"):
            continue
        mod_name = f"uagent.tools.{mname}"
        try:
            if mod_name in sys.modules:
                mod = importlib.reload(sys.modules[mod_name])
            else:
                mod = importlib.import_module(mod_name)
            results.append((mname, mod))
        except Exception:
            continue
    return results


def enable_genre_tools(genre: str) -> list[str]:
    """Enable all tools with the given tool_genre. Returns list of enabled tool names."""
    _ENABLED_GENRES.add(genre)
    from . import _register_tool_module

    changed_names: list[str] = []
    for mname, mod in _find_tool_modules():
        spec = getattr(mod, "TOOL_SPEC", None)
        if not isinstance(spec, dict):
            continue
        if spec.get("tool_genre") != genre:
            continue

        # Force tool_level to 0 so it gets registered as an LLM tool
        spec["tool_level"] = 0

        mod_name = f"uagent.tools.{mname}"
        if _register_tool_module(mod, mod_name):
            func_info = spec.get("function", {})
            tname = func_info.get("name")
            if tname:
                changed_names.append(tname)

    return changed_names


def disable_genre_tools(genre: str) -> list[str]:
    """Disable all tools with the given tool_genre. Returns list of disabled tool names."""
    _ENABLED_GENRES.discard(genre)
    from . import TOOL_SPECS, _RUNNERS, _sort_registered_tools

    removed_names: list[str] = []
    to_remove: list[str] = []

    for spec in TOOL_SPECS:
        if not isinstance(spec, dict):
            continue
        if spec.get("tool_genre") == genre:
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
    return removed_names


def enable_single_tool(tool_name: str, persist: int = -1) -> bool:
    """Enable a single tool by name (regardless of genre).

    Args:
        tool_name: Name of the tool to load.
        persist: Number of uses before auto-unload.
                 -1 = unlimited (session lifetime).
                  0 = immediately expired (do not load).
                 >0 = unload after N uses.

    Returns True if found and loaded.
    """
    if persist == 0:
        return False

    from . import _register_tool_module

    for mname, mod in _find_tool_modules():
        spec = getattr(mod, "TOOL_SPEC", None)
        if not isinstance(spec, dict):
            continue
        func_info = spec.get("function", {})
        if not isinstance(func_info, dict):
            continue
        if func_info.get("name") != tool_name:
            continue

        # Force tool_level to 0 and register
        spec["tool_level"] = 0
        _LOADED_SINGLE_TOOLS[tool_name] = persist
        mod_name = f"uagent.tools.{mname}"
        return _register_tool_module(mod, mod_name)

    return False


def consume_tool_use(tool_name: str) -> None:
    """Decrement remaining uses for an individually loaded tool.
    Call after each tool invocation. Auto-unloads when count reaches 0."""
    if tool_name not in _LOADED_SINGLE_TOOLS:
        return
    remaining = _LOADED_SINGLE_TOOLS[tool_name]
    if remaining == -1:
        return  # unlimited
    remaining -= 1
    if remaining <= 0:
        _LOADED_SINGLE_TOOLS.pop(tool_name, None)
        # Remove from TOOL_SPECS and _RUNNERS
        from . import TOOL_SPECS, _RUNNERS, _sort_registered_tools

        for i, spec in enumerate(TOOL_SPECS):
            if spec.get("function", {}).get("name") == tool_name:
                TOOL_SPECS.pop(i)
                break
        _RUNNERS.pop(tool_name, None)
        _sort_registered_tools()
    else:
        _LOADED_SINGLE_TOOLS[tool_name] = remaining
