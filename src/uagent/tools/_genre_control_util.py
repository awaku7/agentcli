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
    "dev": 1024,
    "web": 2048,
    "utility": 4096,
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

# Per-tool dynamic auto-unload thresholds and Fibonacci state.
# value: (current_threshold, fib_prev, fib_current)
# bump_threshold() adds fib_current and advances the Fibonacci pair.
_TOOL_DYNAMIC_THRESHOLDS: dict[str, tuple[int, int, int]] = {}

# Tools pinned against auto-unload (name -> reason).
# Used by long-lived tools such as browser_playwright while sessions are active.
_PINNED_TOOLS: dict[str, str] = {}


def get_enabled_tool_names() -> list[str]:
    """Return a sorted list of all currently enabled tool names."""
    from . import TOOL_SPECS

    names: list[str] = []
    for spec in TOOL_SPECS:
        func = spec.get("function", {})
        name = func.get("name") if isinstance(func, dict) else None
        if name:
            names.append(str(name))
    names.sort()
    return names


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
            # Do NOT reload existing modules here.
            # Reload wipes module-level state (e.g. browser sessions).
            if mod_name in sys.modules:
                mod = sys.modules[mod_name]
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


def enable_single_tool(tool_name: str, initial_threshold: int = 5) -> bool:
    """Enable a single tool by name (regardless of genre).

    Args:
        tool_name: Name of the tool to load.
        initial_threshold: Initial auto-unload threshold in rounds.
                           Default is 5.

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
        _TOOL_DYNAMIC_THRESHOLDS[tool_name] = (initial_threshold, 0, 1)
        mod_name = f"uagent.tools.{mname}"
        return _register_tool_module(mod, mod_name)

    return False


def get_threshold(tool_name: str) -> int:
    """Return the current auto-unload threshold for a tool (in rounds).

    Returns 0 if the tool is not tracked (no auto-unload).
    """
    data = _TOOL_DYNAMIC_THRESHOLDS.get(tool_name)
    if data is None:
        return 0
    return data[0]


def bump_threshold(tool_name: str, max_threshold: int = 30) -> None:
    """Increase the auto-unload threshold using Fibonacci increments.

    Adds fib_current to the threshold, then advances the Fibonacci pair.
    Caps at max_threshold (default 20).
    """
    data = _TOOL_DYNAMIC_THRESHOLDS.get(tool_name)
    if data is None:
        return
    current, fib_prev, fib_cur = data
    increment = fib_cur
    new_threshold = min(current + increment, max_threshold)
    _TOOL_DYNAMIC_THRESHOLDS[tool_name] = (new_threshold, fib_cur, fib_prev + fib_cur)


def pin_tool(tool_name: str, reason: str = "") -> bool:
    """Prevent *tool_name* from being auto-unloaded.

    Returns True if the pin was newly set or the reason was updated.
    """
    name = str(tool_name or "").strip()
    if not name:
        return False
    _PINNED_TOOLS[name] = str(reason or "")
    return True


def unpin_tool(tool_name: str) -> bool:
    """Allow *tool_name* to be auto-unloaded again.

    Returns True if a pin was removed.
    """
    name = str(tool_name or "").strip()
    if not name:
        return False
    return _PINNED_TOOLS.pop(name, None) is not None


def is_tool_pinned(tool_name: str) -> bool:
    """Return True if *tool_name* is currently pinned against auto-unload."""
    name = str(tool_name or "").strip()
    if not name:
        return False
    return name in _PINNED_TOOLS


def list_pinned_tools() -> dict[str, str]:
    """Return a copy of pinned tools mapping (name -> reason)."""
    return dict(_PINNED_TOOLS)


def disable_single_tool(tool_name: str, force: bool = False) -> bool:
    """Unload a single tool by name. Returns True if found and removed.

    Pinned tools are skipped unless *force* is True.
    On success, also clears management-loop load streaks for this target so
    auto-unload (which never emits unload_tool) does not leave a stale count.
    """
    if not force and is_tool_pinned(tool_name):
        return False
    _LOADED_SINGLE_TOOLS.pop(tool_name, None)
    _TOOL_DYNAMIC_THRESHOLDS.pop(tool_name, None)
    if force:
        _PINNED_TOOLS.pop(tool_name, None)
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
        try:
            from ..uagent_llm import clear_mgmt_load_streak

            clear_mgmt_load_streak(tool_name)
        except Exception:
            # Avoid import/cycle failures blocking unload itself.
            pass
    return found
