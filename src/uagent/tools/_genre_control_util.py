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

_GENRE_BITMAP: dict[str, int] = {
    "basic": 1,
    "comm": 2,
    "office": 4,
    "devel": 8,
    "iot": 16,
    "exec": 32,
    "external": 64,
    "media": 128,
    "file": 256,
    "index": 512,
}


def get_enabled_genre_mask() -> int:
    """Return the bitmask of currently enabled tool genres."""
    mask = 0
    for genre, bit in _GENRE_BITMAP.items():
        if genre in _ENABLED_GENRES:
            mask |= bit
    return mask

# Track individually loaded tools and remaining uses (persists across plugin reloads)
# value: remaining uses (-1 = unlimited, 0 = expired, >0 = countdown)
_LOADED_SINGLE_TOOLS: dict[str, int] = {}


_LAZY_MODULE_NAMES: set[str] = set()


def _is_lazy_module(mname: str) -> bool:
    """Check if a tool module has LAZY_LOAD = True by scanning its source."""
    pkg_dir = os.path.dirname(__file__)
    filepath = os.path.join(pkg_dir, f"{mname}.py")
    if not os.path.isfile(filepath):
        return False
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if "LAZY_LOAD" in line and "True" in line:
                    return True
                # Stop scanning after module-level definitions
                if line.startswith(("def ", "class ", "TOOL_SPEC")):
                    break
    except Exception:
        return False
    return False


def _find_tool_modules(skip_lazy: bool = False) -> list[tuple[str, Any]]:
    """Return (module_name, module) pairs for all discoverable tool modules.

    If skip_lazy is True, modules with LAZY_LOAD = True are not imported
    (used for catalog discovery without importing heavy dependencies).
    """
    pkg_dir = os.path.dirname(__file__)
    results: list[tuple[str, Any]] = []
    for m in pkgutil.iter_modules([pkg_dir]):
        mname = m.name
        # Skip utility/private modules and non-tool files
        if mname.startswith("_") or mname in ("context",):
            continue
        if not mname.endswith("_tool"):
            continue
        if skip_lazy and _is_lazy_module(mname):
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

        # Skip if the module has a missing dependency
        reason = getattr(mod, "LOAD_DISABLED_REASON", "")
        if reason:
            print(
                f"[tools] Skipping {mname}: {reason}",
                file=sys.stderr,
            )
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


def enable_single_tool(tool_name: str) -> bool:
    """Enable a single tool by name (regardless of genre).

    Args:
        tool_name: Name of the tool to load.

    Returns True if found and loaded.
    """
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
        _LOADED_SINGLE_TOOLS[tool_name] = -1
        mod_name = f"uagent.tools.{mname}"
        return _register_tool_module(mod, mod_name)

    return False


def consume_tool_use(tool_name: str) -> None:
    """No-op: persist/use-counting has been removed."""
    pass


def disable_single_tool(tool_name: str) -> bool:
    """Unload a single tool by name. Returns True if found and removed."""
    _LOADED_SINGLE_TOOLS.pop(tool_name, None)
    from . import TOOL_SPECS, _RUNNERS, _sort_registered_tools

    found = False
    for i, spec in enumerate(TOOL_SPECS):
        if spec.get("function", {}).get("name") == tool_name:
            TOOL_SPECS.pop(i)
            found = True
            break
    _RUNNERS.pop(tool_name, None)
    if found:
        _sort_registered_tools()
    return found
