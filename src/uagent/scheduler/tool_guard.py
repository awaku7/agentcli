"""Keep tools required by a scheduled run available during its execution."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator


@contextmanager
def required_tools_guard(
    tool_names: object,
    *,
    reason: str = "scheduled run",
) -> Iterator[tuple[str, ...]]:
    """Load and pin required tools for the lifetime of a scheduled run."""
    if isinstance(tool_names, str):
        names = (tool_names,)
    elif isinstance(tool_names, (list, tuple, set, frozenset)):
        names = tuple(str(name or "").strip() for name in tool_names)
    else:
        names = ()
    names = tuple(dict.fromkeys(name for name in names if name))
    if not names:
        yield ()
        return

    from .. import tools
    from ..tools._genre_control_util import (
        disable_single_tool,
        enable_single_tool,
        is_tool_pinned,
        list_pinned_tools,
        pin_tool,
        unpin_tool,
    )

    previous_pins = list_pinned_tools()
    loaded_here: list[str] = []
    pinned_here: list[str] = []
    try:
        visible_names = set()
        for spec in tools.get_tool_specs() or []:
            if not isinstance(spec, dict):
                continue
            fn = spec.get("function") or {}
            name = fn.get("name") if isinstance(fn, dict) else spec.get("name")
            if name:
                visible_names.add(str(name))

        for name in names:
            if name not in visible_names:
                if not enable_single_tool(name):
                    raise RuntimeError(
                        f"required scheduled tool is unavailable: {name}"
                    )
                loaded_here.append(name)
                visible_names.add(name)
            if not is_tool_pinned(name):
                pin_tool(name, reason=f"{reason}:{name}")
                pinned_here.append(name)
        yield names
    finally:
        for name in reversed(pinned_here):
            unpin_tool(name)
            if name in previous_pins:
                pin_tool(name, previous_pins[name])
        for name in reversed(loaded_here):
            try:
                disable_single_tool(name)
            except Exception:
                pass


__all__ = ["required_tools_guard"]
